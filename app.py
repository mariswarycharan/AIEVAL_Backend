from fastapi import FastAPI
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


genai.configure(api_key='AIzaSyCs_29YQezoMFeogrFqfyjZ0ViGMxgt4ws')

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


class InputData(BaseModel):
    user_id: str = "123456789"


# Create the model
generation_config = {
  "temperature": 0.5,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 10000,
  "response_schema": content.Schema(
    type = content.Type.OBJECT,
    description = "Comprehensive evaluation of student's answers including raw generated text and the final score.",
    required = ["generated_text", "final_score"],
    properties = {
      "generated_text": content.Schema(
        type = content.Type.STRING,
        description = "The raw generated text from the model, containing the detailed evaluation and feedback for each question.",
      ),
      "final_score": content.Schema(
        type = content.Type.INTEGER,
        description = "The final cumulative score awarded to the student, representing the sum of scores across all evaluated questions.",
      ),
    },
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


@app.get("/get_result")
async def submit_form():
    
    context = """
    1. What is the goal of prediction?
The goal of prediction is to predict a quantity
2. List few prediction algorithms.
Linear regression, polynomial regression, support vector regression
""" 
    
    input_value = """
    1. What is the goal of prediction?
The goal of prediction is to predict a quality of water
2. List few prediction algorithms.
Linear regression, polynomial regression, support mass regression
"""
    
    prompt_template = f"""
You are a highly intelligent and meticulous academic AI assistant tasked with evaluating student answer sheets. Your primary objective is to perform a fair, thorough, and insightful assessment of student responses based on three critical criteria: Relevance, Correctness, and Depth of Knowledge. Your evaluation should not only determine if the student’s response is correct but also consider how well the student has understood and articulated the underlying concepts.

**Evaluation Criteria:**
1. **Relevance**: Evaluate the extent to which the student’s response directly addresses the question posed. Consider whether the answer stays on topic and fulfills the requirements of the question.
2. **Correctness**: Assess the accuracy of the information provided by the student. This includes checking facts, figures, and any technical details to ensure the response is factually correct and logically sound.
3. **Depth of Knowledge**: Analyze the depth and breadth of the student’s understanding as demonstrated in the response. Look for insightful explanations, connections to broader concepts, and a clear demonstration of mastery over the subject matter.

**Scoring Instructions:**
- Allocate a maximum of 2 marks per question, considering all three criteria together.
- If a student has answered multiple questions, sum up the marks awarded for each question and provide a final score in the format: *Student scored X/Total Marks*.

**Process:**
1. Begin by semantically comparing the student's response to the original answer key.
2. Reason through the answer step by step to determine if the student has given a correct and relevant response.
3. If an answer is incorrect or incomplete, provide a brief explanation highlighting the inaccuracies or missing elements.
4. After evaluating each question individually, sum up the marks to provide a final score.

**Original Answer Key:**
{context}

**Student's Written Answer:**
{input_value}

Evaluate the student's answers, allocate up to 2 marks per question based on the overall assessment, provide justifications for the marks awarded, and calculate the final score. If there are 10 questions, for example, you should present the final score as *Student scored X/20* (with 20 being the total possible marks for 10 questions).

"""
    
    result = get_result_from_gemini(prompt=prompt_template.format(context=context, input_value=input_value),image_list=[])
    return {"result": json.loads(result)}


    