from fastapi import FastAPI
import google.generativeai as genai
from typing import List
from pydantic import BaseModel
import os
from fastapi.middleware.cors import CORSMiddleware
from google.ai.generativelanguage_v1beta.types import content
from fastapi import FastAPI, Form

app = FastAPI()
    

genai.configure(api_key='AIzaSyCN8bK-8lFUKTxMd2dBEgSSIPBsHEbnYig')

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
  "temperature": 0.2,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 10000,
  "response_schema": content.Schema(
    type = content.Type.OBJECT,
    description = "Evaluate student's answers based on Relevance, Correctness, and Depth of Knowledge, allocate marks, and provide a final score",
    properties = {
      "question_evaluations": content.Schema(
        type = content.Type.ARRAY,
        description = "List of evaluations for each question",
        items = content.Schema(
          type = content.Type.OBJECT,
          properties = {
            "question_number": content.Schema(
              type = content.Type.INTEGER,
              description = "The number of the question being evaluated",
            ),
            "relevance_score": content.Schema(
              type = content.Type.NUMBER,
              description = "Score for relevance criterion",
            ),
            "correctness_score": content.Schema(
              type = content.Type.NUMBER,
              description = "Score for correctness criterion",
            ),
            "depth_of_knowledge_score": content.Schema(
              type = content.Type.NUMBER,
              description = "Score for depth of knowledge criterion",
            ),
            "total_score": content.Schema(
              type = content.Type.NUMBER,
              description = "Total score for the question",
            ),
            "justification": content.Schema(
              type = content.Type.STRING,
              description = "Justification for the score awarded",
            ),
          },
        ),
      ),
      "final_score": content.Schema(
        type = content.Type.STRING,
        description = "Final score for the student, presented as 'Student scored X/Total Marks'",
      ),
    },
  ),
  "response_mime_type": "application/json",
}


# @param ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-1.0-pro"]
model = genai.GenerativeModel('models/gemini-1.5-flash',generation_config=generation_config)
    
def get_result_from_gemini(prompt):
    global model
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
    
    result = get_result_from_gemini(prompt=prompt_template.format(context=context, input_value=input_value))
    return {"result": result}


    