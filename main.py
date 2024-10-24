from fastapi import FastAPI ,Query
import google.generativeai as genai
from typing import List
from pydantic import BaseModel
import json
import os
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import requests
from io import BytesIO
from google.ai.generativelanguage_v1beta.types import content
from fastapi import FastAPI, Form
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

gemini_api_key = os.environ.get("GEMINI_API_KEY")
# Get the Supabase URL and Key
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def get_answer_key_and_student_response(qap_id: str, email_id: str) -> str:
    answer_key = supabase.table("QATABLE").select("qap").eq("exam_id", qap_id).execute()
    student_response = supabase.table("RESPONSES").select("answers").eq("email",email_id).eq("exam_id", qap_id).execute()
    answer_key_data = answer_key.data[0]
    student_response_data = student_response.data[0]
    final_answer_key_data = ""
    for num,i in enumerate(answer_key_data['qap']):
        final_answer_key_data += f"This is original question,answer,prompt(prompt is used for evaluating the answer how you want to evaluate it for question no. {str(num + 1)} ) and mark(mark is for perticular mark allocated for this question) for question number {str(num + 1)} \n " 
        final_answer_key_data +=  "Question : " + i['question'] + '\n'
        final_answer_key_data += "Answer : " + i['answer'] + '\n'
        final_answer_key_data += "Prompt : " + i['prompt'] + '\n'
        final_answer_key_data += "Mark : " + str(i['marks']) + '\n'
        final_answer_key_data += "-" * 60
        
        
    final_student_response_data = ""
    for index, (ques, ans) in enumerate(zip(answer_key.data[0]['qap'], list(student_response.data[0]['answers'].values()))):
        final_student_response_data += "This is student written question and answer for question number " + str(index + 1) + "\n"
        final_student_response_data += "Question : " + ques['question'] + '\n'
        final_student_response_data += "Answer : " + ans + '\n'
        final_student_response_data += "-" * 60
        
    return final_answer_key_data, final_student_response_data
    
genai.configure(api_key=gemini_api_key)

app = FastAPI()

origins = [
    "http://10.1.75.50:3000",
    "http://10.1.90.220:3000",
    "https://i-open-roche.vercel.app",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://0.0.0.0:8000",
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
        type = content.Type.STRING,
        description = "The final cumulative score awarded to the student, summarizing the total score in the format 'Student scored X/Y'."
      )
    }
  ),
  "response_mime_type": "application/json",
}

# @param ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-1.0-pro"]
model = genai.GenerativeModel('models/gemini-1.5-flash',generation_config=generation_config)
    
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
    email_ip : str = ""

@app.post("/get_result")
async def submit_form(data: InputData):
    
    qap_id = data.qap_id
    email_ip = data.email_ip
    
    answer_key , student_response = get_answer_key_and_student_response(qap_id,email_ip)
    
    answer_key +=  """
    This is original question,answer,prompt(prompt is used for evaluating the answer how you want to evaluate it for question no. 2 ) and mark(mark is for perticular mark allocated for this question) for question number 2 
Question : what is data science
Answer : Data science is a multidisciplinary field that uses modern tools and techniques to analyze large amounts of data and extract knowledge from it. The goal of data science is to use the insights gained from data to solve problems and make decisions in a variety of fields   
Prompt : 10 words
Mark : 5
"""
    student_response +=  """
    This is student written question and answer for question number 2
    Question : what is data science
    Answer : Data science is a sports game"""
    
    
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

    return {"result": json.loads(result)}


    