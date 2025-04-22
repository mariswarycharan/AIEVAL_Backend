from fastapi import FastAPI ,Query, UploadFile, File
import google.generativeai as genai
from typing import List
from pydantic import BaseModel
import json
import os
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import fitz  # PyMuPDF
import glob
from fastapi.staticfiles import StaticFiles
import requests
from io import BytesIO
from google.ai.generativelanguage_v1beta.types import content
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client
from fastapi.responses import FileResponse
from datetime import datetime
from pymongo import MongoClient
import gridfs
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Frame, PageTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.units import inch, cm
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from io import BytesIO

load_dotenv()

gemini_api_key = os.environ.get("GEMINI_API_KEY")
# Get the Supabase URL and Key
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def generate_pdf(qap_id: str, email_id: str, student_name: str, exam_name: str, result_data: dict, answer_key_data: list, student_response_data: dict):

    buffer = BytesIO()

    # Setup the document with border frame
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=30, leftMargin=30,
                            topMargin=40, bottomMargin=30)

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Title'], fontSize=18, alignment=TA_CENTER, textColor=colors.darkblue)
    heading_style = ParagraphStyle('HeadingStyle', parent=styles['Heading2'], fontSize=12, spaceBefore=8, spaceAfter=4, textColor=colors.darkred)
    question_style = ParagraphStyle('QuestionStyle', parent=styles['BodyText'], fontSize=11, fontName='Helvetica-Bold')
    answer_style = ParagraphStyle('AnswerStyle', parent=styles['BodyText'], fontSize=10, leftIndent=15)
    normal_style = ParagraphStyle('NormalStyle', parent=styles['BodyText'], fontSize=10, spaceBefore=4)
    feedback_style = ParagraphStyle('FeedbackStyle', parent=styles['BodyText'], fontSize=9, leftIndent=10, rightIndent=5, spaceBefore=3)

    # Header block
    total_marks = sum(q['marks'] for q in answer_key_data)
    final_score = result_data.get('final_score', 0)

    content = []
    content.append(Paragraph("Examination Report", title_style))
    content.append(Spacer(1, 0.2 * inch))

    header_data = [
        ['Exam Name:', exam_name, 'Date:', datetime.now().strftime("%d-%m-%Y")],
        ['Student Name:', student_name, 'Score:', f"{final_score}/{total_marks}"],
        ['Email ID:', email_id, 'Exam ID:', qap_id]
    ]
    header_table = Table(header_data, colWidths=[80, 200, 80, 150])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    content.append(header_table)
    content.append(Spacer(1, 0.3 * inch))

    content.append(Paragraph("Answer-wise Breakdown", heading_style))
    content.append(Spacer(1, 0.1 * inch))

    # Question loop
    for item in result_data['result']:
        qn = item['question_number']
        mark_awarded = item['mark']
        justification = item['justification']
        question_text = answer_key_data[qn - 1]['question']
        max_marks = answer_key_data[qn - 1]['marks']
        student_answer = list(student_response_data.values())[qn - 1]

        content.append(Paragraph(f"Q{qn}: {question_text}", question_style))
        content.append(Paragraph(f"Student's Answer: {student_answer}", answer_style))

        score_just_table = Table([
            [Paragraph(f"<b>Score:</b> {mark_awarded}/{max_marks}", normal_style)],
            [Paragraph(f"<b>Feedback:</b> {justification}", feedback_style)]
        ], colWidths=[460])
        score_just_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (0, 0), colors.lightgrey),
            ('BACKGROUND', (0, 1), (0, 1), colors.whitesmoke),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        content.append(score_just_table)
        content.append(Spacer(1, 0.2 * inch))

    # Summary block
    summary = Table([["FINAL SCORE", f"{final_score}/{total_marks}"]], colWidths=[240, 240])
    summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightblue),
        ('BOX', (0, 0), (-1, -1), 1, colors.darkblue),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    content.append(Spacer(1, 0.4 * inch))
    content.append(summary)

    doc.build(content)
    
    buffer.seek(0) # reset buffer position to the beginning
    return buffer

def upload_pdf_to_mongodb(pdf_buffer: BytesIO, filename: str):
    """
    Uploads a PDF file to MongoDB using GridFS.

    :param pdf_path: Path to the PDF file (string)
    :return: The file ID assigned by GridFS
    """
        
    MONGO_URI = os.environ.get("MONGO_URI")
    DATABASE_NAME = "examinationreports"

    # Connect to MongoDB
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]

    # Initialize GridFS
    fs = gridfs.GridFS(db)

    # Reset buffer position
    pdf_buffer.seek(0)

    # Upload the buffer directly to GridFS
    file_id = fs.put(pdf_buffer, filename=filename)

    print(f"PDF uploaded successfully to MongoDB. File ID: {file_id}")
    return file_id

def upload_pdf_to_gdrive(pdf_buffer: BytesIO, filename: str):
    """
    Uploads a PDF file to Google Drive and makes it publicly viewable using credentials from .env

    :param pdf_path: Path to the PDF file
    :return: Shareable public link to the PDF
    """

    # Build service account info dict
    service_account_info = {
        "type": "service_account",
        "project_id": os.environ.get("GOOGLE_PROJECT_ID"),
        "private_key_id": os.environ.get("GOOGLE_PRIVATE_KEY_ID"),
        "private_key": os.environ.get("GOOGLE_PRIVATE_KEY").replace('\\n', '\n'),
        "client_email": os.environ.get("GOOGLE_CLIENT_EMAIL"),
        "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.environ.get('GOOGLE_CLIENT_EMAIL')}",
        "universe_domain": "googleapis.com"
    }

    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)

    # Build the Google Drive service
    service = build('drive', 'v3', credentials=creds)

    # Upload the file
    file_metadata = {
        'name': filename,
        'mimeType': 'application/pdf'
    }
    media = MediaIoBaseUpload(pdf_buffer, mimetype='application/pdf')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = file.get('id')

    # Make the file public
    service.permissions().create(
        fileId=file_id,
        body={'role': 'reader', 'type': 'anyone'},
    ).execute()

    # Get the shareable link
    shareable_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
    print(f"PDF uploaded to Google Drive. Shareable link: {shareable_link}")
    return shareable_link

def get_answer_key_and_student_response(qap_id: str, email_id: str) -> str:
  
    response_answer_key = supabase.table("QATABLE").select("qap","exam_name").eq("question_paper_id", qap_id).execute()
    answer_key = response_answer_key.data[0]['qap']
    exam_name = response_answer_key.data[0]['exam_name']
    
    student_response = supabase.table("RESPONSES").select("answers").eq("email",email_id).eq("qid", qap_id).execute()

    answer_key_data = answer_key
    student_response_data = student_response.data[0]['answers']
    
    final_answer_key_data = ""
    for num,i in enumerate(answer_key_data):
        final_answer_key_data += f"This is original question,answer,prompt(prompt is used for evaluating the answer how you want to evaluate it for question no. {str(num + 1)} ) and mark(mark is for perticular mark allocated for this question) for question number {str(num + 1)} \n " 
        final_answer_key_data +=  "Question : " + i['question'] + '\n'
        final_answer_key_data += "Answer : " + i['answer'] + '\n'
        final_answer_key_data += "Prompt : " + i['prompt'] + '\n'
        final_answer_key_data += "Mark : " + str(i['marks']) + '\n'
        final_answer_key_data += "-" * 60
        
        
    final_student_response_data = ""
    for index, (ques, ans) in enumerate(zip(answer_key, list(student_response.data[0]['answers'].values()))):
        final_student_response_data += "This is student written question and answer for question number " + str(index + 1) + "\n"
        final_student_response_data += "Question : " + ques['question'] + '\n'
        final_student_response_data += "Answer : " + ans + '\n'
        final_student_response_data += "-" * 60
        
    return final_answer_key_data, final_student_response_data , exam_name , answer_key , student_response_data
    
genai.configure(api_key=gemini_api_key)

app = FastAPI()

origins = [
    "http://10.1.75.50:3000",
    "http://10.1.90.220:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://0.0.0.0:8000",
    "http://localhost:3000",
    "https://aieval.vercel.app",
    "https://aieval-final.vercel.app"   
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def status_check():    
    return {"status": "Healthy and running project is on live"}

# Create the model
generation_config = {
  "temperature": 0.5,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 10000,
  "response_schema": content.Schema(
    type = content.Type.OBJECT,
    description = "Comprehensive evaluation of student's answers including detailed question-wise results and final score.",
    required = ["result", "final_score"],
    properties = {
      "result": content.Schema(
        type = content.Type.ARRAY,
        description = "An array containing detailed evaluation of each question.",
        items = content.Schema(
          type = content.Type.OBJECT,
          required = ["question_number", "mark", "justification"],
          properties = {
            "question_number" : content.Schema(
              type = content.Type.INTEGER,
              description = "The question number for each question."
            ),
            "mark" : content.Schema(
              type = content.Type.INTEGER,
              description = "The mark awarded for each question."
            ),
            "justification": content.Schema(
              type = content.Type.STRING,
              description = "The raw generated justification from the model, containing the detailed evaluation and feedback for each question."
            )
          }
        )
      ),
      "final_score": content.Schema(
        type = content.Type.INTEGER,
        description = "The final cumulative score awarded to the student, finally give the total score in the integer type ( just only score he got ) ''."
      )
    }
  ),
  "response_mime_type": "application/json",
}

# @param ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-1.0-pro"]
model = genai.GenerativeModel('models/gemini-2.0-flash',generation_config=generation_config)
    
def get_result_from_gemini(prompt,image_list):
    global model
    list_of_images = []
    
    for image in image_list:
      response = requests.get(image)
      img = Image.open(BytesIO(response.content))
      list_of_images.append(img)
      
    if list_of_images:
        response = model.generate_content(list_of_images + prompt)
        return response.text
    else:
        response = model.generate_content(prompt)
        return response.text

class InputData(BaseModel):
    qap_id : str = ""
    email_id : str = ""

# Serve the static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/favicon.ico")
async def favicon():
    return FileResponse(os.path.join("static", "favicon.ico"))

@app.post("/get_result")
async def submit_form(data: InputData):
    
    print("Data received")
    print(data)
    qap_id = data.qap_id
    email_id = data.email_id
    
    if not qap_id or not email_id:
        raise HTTPException(status_code=400, detail="Missing qap_id or email_id")
    
    answer_key , student_response , exam_name , answer_key , student_response_data = get_answer_key_and_student_response(qap_id,email_id)

#     answer_key +=  """
#     This is original question,answer,prompt(prompt is used for evaluating the answer how you want to evaluate it for question no. 2 ) and mark(mark is for perticular mark allocated for this question) for question number 2 
# Question : what is data science
# Answer : Data science is a multidisciplinary field that uses modern tools and techniques to analyze large amounts of data and extract knowledge from it. The goal of data science is to use the insights gained from data to solve problems and make decisions in a variety of fields   
# Prompt : 10 words
# Mark : 5
# """
#     student_response +=  """
#     This is student written question and answer for question number 2
#     Question : what is data science
#     Answer : Data science is a sports game"""
    
    json_format = """
    {
      result: [
        {question_number : _________ ,
        mark : __________ ,
        justification : __________ ,
        },
        {question_number : _________ ,
        mark : __________ ,
        justification : __________ ,
        },
        etc...
        
      ],
      final_score : __________,
    }
    """
    
    prompt_template = f"""
You are a highly intelligent and meticulous academic AI assistant tasked with evaluating student answer sheets. Your primary objective is to perform a fair, thorough, and insightful assessment of student responses based on three critical criteria: Relevance, Correctness, and Depth of Knowledge. Your evaluation should not only determine if the student’s response is correct but also consider how well the student has understood and articulated the underlying concepts.

**Evaluation Criteria:**
1. **Relevance**: Evaluate the extent to which the student’s response directly addresses the question posed. Consider whether the answer stays on topic and fulfills the requirements of the question.
2. **Correctness**: Assess the accuracy of the information provided by the student. This includes checking facts, figures, and any technical details to ensure the response is factually correct and logically sound.
3. **Depth of Knowledge**: Analyze the depth and breadth of the student’s understanding as demonstrated in the response. Look for insightful explanations, connections to broader concepts, and a clear demonstration of mastery over the subject matter.

**Scoring Instructions:**
- Allocate marks for each question (marks are given for each question in answer key) based on the above criteria.
- If a student has answered multiple questions, sum up the marks awarded for each question and provide a final score in the format: *Student scored X/Total Marks*.

**Process:**
1. Begin by semantically comparing the student's response to the original answer key.
2. Reason through the answer step by step to determine if the student has given a correct and relevant response.
3. If an answer is incorrect or incomplete, provide a brief explanation highlighting the inaccuracies or missing elements.
4. After evaluating each question individually, sum up the marks to provide a final score.

**Original Answer Key:**
{answer_key}

**Student's Written Answer:**
{student_response}

Evaluate the student's answers, allocate marks per question based on the overall assessment, provide justifications for the marks awarded, and calculate the final score. If there are 10 questions, for example, you should present the final score as *Student scored X/20* (with 20 being the total possible marks for 10 questions).
Make the outputs in given JSON format.
{json_format}
"""
    
    try:
        result = get_result_from_gemini(prompt=prompt_template,image_list=[])
        # print("Raw result from Gemini:\n", result)
        result_json = json.loads(result)
    except Exception as e:
        print("Gemini or JSON Error:", str(e))
        raise HTTPException(status_code=500, detail="Gemini response or JSON parsing failed.")
    
    # Fetch additional information needed for PDF generation
    student_name = supabase.table("STUDENT").select("uname").eq("email", email_id).execute().data[0]['uname']    
    
    # Parse the answer key and student response for PDF generation
    answer_key_data = answer_key
    
    student_response_data = student_response_data
    
    # Generate PDF
    try:
        pdf_buffer = generate_pdf(
            qap_id=qap_id,
            email_id=email_id,
            student_name=student_name,
            exam_name=exam_name,
            result_data=result_json,
            answer_key_data=answer_key_data,
            student_response_data=student_response_data
        )
        print("PDF generated in memory.")
    except Exception as e:
        print("PDF Generation Error:", str(e))
        raise HTTPException(status_code=500, detail="PDF generation failed.")

    filename = f"{email_id}_{qap_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    # store pdf in mongodb
    # try:
    #     file_id = upload_pdf_to_mongodb(pdf_buffer=pdf_buffer, filename=filename)
    # except Exception as e:
    #     print("MongoDB Upload Error:", str(e))
    #     raise HTTPException(status_code=500, detail="MongoDB upload failed.")
    
    # store pdf in google drive
    try:
        uploaded_url = upload_pdf_to_gdrive(pdf_buffer=pdf_buffer, filename=filename)
    except Exception as e:
        print("Drive Upload Error:", str(e))
        raise HTTPException(status_code=500, detail="Google Drive upload failed.")
    
    return {"result": result_json , "examination_report" : uploaded_url }

def read_pdf_content(file: UploadFile) -> str:
    # Read PDF content using PyMuPDF
    text = ""
    with fitz.open(stream=file.file.read(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text

def generate_exam_report_pdf_for_upload_type(student_name, exam_title, result_json):
    buffer = BytesIO()

    # Setup the document with border frame
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=30, leftMargin=30,
                            topMargin=40, bottomMargin=30)

    styles = getSampleStyleSheet()
    custom_style = ParagraphStyle(
        name='CustomBodyText',
        parent=styles['BodyText'],
        fontSize=10,
        leading=14,
        wordWrap='CJK',
        alignment=0
    )

    elements = []

    # Header
    title_style = styles['Title']
    title_style.textColor = colors.darkblue
    elements.append(Paragraph(exam_title, title_style))
    elements.append(Spacer(1, 0.2 * inch))

    # Student Info
    elements.append(Paragraph(f"<b>Student Name:</b> {student_name}", styles['Heading3']))
    elements.append(Spacer(1, 0.1 * inch))

    # Table Header
    table_data = [[
        Paragraph("<b>Q. No</b>", styles['Normal']),
        Paragraph("<b>Mark</b>", styles['Normal']),
        Paragraph("<b>Feedback</b>", styles['Normal'])
    ]]

    for item in result_json['result']['result']:
        question_number = str(item['question_number'])
        mark = str(item['mark'])
        justification = Paragraph(item['justification'], custom_style)
        table_data.append([question_number, mark, justification])

    # Table Style
    table = Table(table_data, colWidths=[0.8 * inch, 0.8 * inch, 5.5 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 0.3 * inch))

    # Final Score
    final_score = result_json['result']['final_score']
    elements.append(Paragraph(f"<b>Final Score:</b> {final_score}", styles['Heading3']))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

@app.post("/upload-answers/")
async def upload_pdfs(
    student_name: str = Form(...),
    exam_name: str = Form(...),
    answer_key_file: UploadFile = File(...),
    student_response_file: UploadFile = File(...)
):
    # Validate file types
    if answer_key_file.content_type != "application/pdf" or student_response_file.content_type != "application/pdf":
        return {"error": "Both files must be PDF format"}

    # Read contents
    answer_key = read_pdf_content(answer_key_file)
    student_response = read_pdf_content(student_response_file)

    json_format = """
    {
      result: [
        {question_number : _________ ,
        mark : __________ ,
        justification : __________ ,
        },
        {question_number : _________ ,
        mark : __________ ,
        justification : __________ ,
        },
        etc...
        
      ],
      final_score : __________,
    }
    """
    
    prompt_template = f"""
You are a highly intelligent and meticulous academic AI assistant tasked with evaluating student answer sheets. Your primary objective is to perform a fair, thorough, and insightful assessment of student responses based on three critical criteria: Relevance, Correctness, and Depth of Knowledge. Your evaluation should not only determine if the student’s response is correct but also consider how well the student has understood and articulated the underlying concepts.

**Evaluation Criteria:**
1. **Relevance**: Evaluate the extent to which the student’s response directly addresses the question posed. Consider whether the answer stays on topic and fulfills the requirements of the question.
2. **Correctness**: Assess the accuracy of the information provided by the student. This includes checking facts, figures, and any technical details to ensure the response is factually correct and logically sound.
3. **Depth of Knowledge**: Analyze the depth and breadth of the student’s understanding as demonstrated in the response. Look for insightful explanations, connections to broader concepts, and a clear demonstration of mastery over the subject matter.

**Scoring Instructions:**
- Allocate marks for each question (marks are given for each question in answer key) based on the above criteria.
- If a student has answered multiple questions, sum up the marks awarded for each question and provide a final score in the format: *Student scored X/Total Marks*.

**Process:**
1. Begin by semantically comparing the student's response to the original answer key.
2. Reason through the answer step by step to determine if the student has given a correct and relevant response.
3. If an answer is incorrect or incomplete, provide a brief explanation highlighting the inaccuracies or missing elements.
4. After evaluating each question individually, sum up the marks to provide a final score.

**Original Answer Key:**
{answer_key}

**Student's Written Answer:**
{student_response}

Evaluate the student's answers, allocate marks per question based on the overall assessment, provide justifications for the marks awarded, and calculate the final score. If there are 10 questions, for example, you should present the final score as *Student scored X/20* (with 20 being the total possible marks for 10 questions).
Make the outputs in given JSON format.
{json_format}
"""
    
    try:
        result = get_result_from_gemini(prompt=prompt_template,image_list=[])
        # print("Raw result from Gemini:\n", result)
        result_json = json.loads(result)
    except Exception as e:
        print("Gemini or JSON Error:", str(e))
        raise HTTPException(status_code=500, detail="Gemini response or JSON parsing failed.")
    
    # Generate PDF
    try:
        pdf_buffer = generate_exam_report_pdf_for_upload_type(
            student_name=student_name,
            exam_title=exam_name,
            result_json={ "result" : result_json }
        )
        print("PDF generated in memory.")
    except Exception as e:
        print("PDF Generation Error:", str(e))
        raise HTTPException(status_code=500, detail="PDF generation failed.")

    filename = f"{student_name}_{exam_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    # store pdf in mongodb
    # try:
    #     file_id = upload_pdf_to_mongodb(pdf_buffer=pdf_buffer, filename=filename)
    # except Exception as e:
    #     print("MongoDB Upload Error:", str(e))
    #     raise HTTPException(status_code=500, detail="MongoDB upload failed.")
    
    # store pdf in google drive
    try:
        uploaded_url = upload_pdf_to_gdrive(pdf_buffer=pdf_buffer, filename=filename)
    except Exception as e:
        print("Drive Upload Error:", str(e))
        raise HTTPException(status_code=500, detail="Google Drive upload failed.")
    
    return {"result": result_json , "examination_report" : uploaded_url }

