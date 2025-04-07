from fastapi import FastAPI ,Query
import google.generativeai as genai
from typing import List
from pydantic import BaseModel
import json
import os
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import glob
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
from googleapiclient.http import MediaFileUpload


load_dotenv()

gemini_api_key = os.environ.get("GEMINI_API_KEY")
# Get the Supabase URL and Key
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def generate_pdf(qap_id: str, email_id: str, student_name: str, exam_name: str, result_data: dict, answer_key_data: list, student_response_data: dict):

    # Create a unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_dir = "exam_reports"
    os.makedirs(pdf_dir, exist_ok=True)
    filename = f"{pdf_dir}/{email_id}_{qap_id}_{timestamp}.pdf"

    # Setup the document with border frame
    doc = SimpleDocTemplate(filename, pagesize=A4,
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
    return filename

def upload_pdf_to_mongodb(pdf_path):
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

    # Upload the PDF file
    with open(pdf_path, "rb") as f:
        file_id = fs.put(f, filename=pdf_path.split("/")[-1])
    
    print(f"PDF uploaded successfully. File ID: {file_id}")
    return file_id

def upload_pdf_to_gdrive(pdf_path):
    """
    Uploads a PDF file to Google Drive and makes it publicly viewable using credentials from .env

    :param pdf_path: Path to the PDF file
    :return: Shareable public link to the PDF
    """

    # Build service account info dict
    service_account_info = {
        "type": "service_account",
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
        "private_key": os.getenv("GOOGLE_PRIVATE_KEY").replace('\\n', '\n'),
        "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.getenv('GOOGLE_CLIENT_EMAIL')}",
        "universe_domain": "googleapis.com"
    }

    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)

    # Build the Google Drive service
    service = build('drive', 'v3', credentials=creds)

    # Upload the file
    file_metadata = {
        'name': os.path.basename(pdf_path),
        'mimeType': 'application/pdf'
    }
    media = MediaFileUpload(pdf_path, mimetype='application/pdf')
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
    "https://aieval.vercel.app"   
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
model = genai.GenerativeModel('models/gemini-2.0-flash-thinking-exp-01-21',generation_config=generation_config)
    
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

@app.post("/get_result")
async def submit_form(data: InputData):
    
    print("Data received")
    print(data)
    qap_id = data.qap_id
    email_id = data.email_id
    
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
    
    result = get_result_from_gemini(prompt=prompt_template,image_list=[])
    
    result_json = json.loads(result)
    
    # Fetch additional information needed for PDF generation
    student_name = supabase.table("STUDENT").select("uname").eq("email", email_id).execute().data[0]['uname']    
    
    # Parse the answer key and student response for PDF generation
    answer_key_data = answer_key
    
    student_response_data = student_response_data
    
    # Generate PDF
    pdf_path = generate_pdf(
        qap_id=qap_id,
        email_id=email_id,
        student_name=student_name,
        exam_name=exam_name,
        result_data=result_json,
        answer_key_data=answer_key_data,
        student_response_data=student_response_data
    )
    
    # store pdf in mongodb
    # file_id = upload_pdf_to_mongodb(pdf_path)
    
    # store pdf in google drive
    credentials_path = "gen-lang-client-0901781875-4b0162e138f0.json"
    uploaded_url = upload_pdf_to_gdrive(pdf_path=pdf_path, credentials_path= credentials_path)
    
    return {"result": result_json , "examination_report" : uploaded_url }


@app.get("/download_pdf/{qap_id}/{email_id}")
async def download_pdf(qap_id: str, email_id: str):
    """
    Download the generated PDF for a specific exam and student
    """
    pdf_dir = "exam_reports"
    # Find the most recent PDF for this student and exam
    
    pattern = f"{pdf_dir}/{email_id}_{qap_id}_*.pdf"
    matching_files = glob.glob(pattern)
    
    if not matching_files:
        raise HTTPException(status_code=404, detail="PDF not found")
    
    # Get the most recent file
    latest_file = max(matching_files, key=os.path.getctime)
    
    return FileResponse(
        path=latest_file,
        filename=os.path.basename(latest_file),
        media_type="application/pdf"
    )


    