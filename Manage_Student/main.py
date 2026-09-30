from fastapi import FastAPI
import json
from typing import List, Dict, Annotated

# Path parameter class in fastapi
from fastapi import Path

# HTTP Exception class in fastapi for http status codes
from fastapi import HTTPException

# Query class from fastapi for query endpoints
from fastapi import Query

# import BaseModel class from Pydantic for data validation
from pydantic import BaseModel, Field
from pydantic import field_validator, computed_field

# import JSONResposne to return the data to client or provide response from server
from fastapi.responses import JSONResponse

app = FastAPI()

# helper function

def load_data():
    with open('Students.json', 'r') as f:
        data = json.load(f)
    return data

def save_data(data):
    with open('Students.json', 'a') as f:
        json.dump(data, f)

# create a pydantic data and type valication base model
class student(BaseModel):
    id: Annotated[str,  Field(..., max_length=4, title='student\'s ID', description='Students ID not more than 4 characters', examples=['P001'])]
    name: Annotated[str, Field(..., max_length=50, title='student\'s Full Name', description='Name of the student not more than 50 characters', examples=['Prashant Kumar'])]
    city: Annotated[str, Field(..., max_length=100, title='City Name', description='Name of city or nearest city the student belong to.', examples=['Mohali'])]
    age: Annotated[int, Field(..., gt=0, lt=120 , title='Age of the student', description='Enter age of the student if newly born then 1.', examples=[1,12,35])]
    gender: Annotated[str, Field(..., max_lenght=10)]
    height: Annotated[float, Field(..., gt=0)]
    weight: Annotated[float, Field(..., gt=0)]

    @computed_field
    @property
    def bmi(self) -> float:
        bmi = round(self.weight/(self.height**2), 2)
        return bmi

    @computed_field
    @property
    def verdict(self) -> str:
        if self.bmi < 18.5: return 'Underweight'
        elif self.bmi < 25: return 'Normal'
        elif self.bmi < 30: return 'Overweight'
        else: return 'Obese'

# create a pydantic data and type valication base model
class student(BaseModel):
    id: Annotated[str,  Field(..., max_length=4, title='student\'s ID', description='Students ID not more than 4 characters', examples=['P001'])]
    name: Annotated[str, Field(..., max_length=50, title='student\'s Full Name', description='Name of the student not more than 50 characters', examples=['Prashant Kumar'])]
    city: Annotated[str, Field(..., max_length=100, title='City Name', description='Name of city or nearest city the student belong to.', examples=['Mohali'])]
    age: Annotated[int, Field(..., gt=0, lt=120 , title='Age of the student', description='Enter age of the student if newly born then 1.', examples=[1,12,35])]
    gender: Annotated[str, Field(..., max_lenght=10)]
    height: Annotated[float, Field(..., gt=0)]
    weight: Annotated[float, Field(..., gt=0)]

    @computed_field
    @property
    def bmi(self) -> float:
        bmi = round(self.weight/(self.height**2), 2)
        return bmi

    @computed_field
    @property
    def verdict(self) -> str:
        if self.bmi < 18.5: return 'Underweight'
        elif self.bmi < 25: return 'Normal'
        elif self.bmi < 30: return 'Overweight'
        else: return 'Obese'


@app.get("/")
def welcome():
    return {'message':'Welcome to Students Mangement System API'}

@app.get("/about")
def about():
    return {'message':'A fully functional API whose endpoint is /about'}

@app.get("/view")
def view():
    data = load_data()
    return data

# Path Parameter
'''The Path() function in FastAPI is used to provide metadata, validation rules, and documentation hints for path parameter in you API endpoints

Title, Description, Example, ge, gt, le, lt, Min_length, Max_length, Regex
'''

# to get the student details with student id
@app.get("/student/{student_id}")
def view_students_via_id(student_id: str = Path(..., description='ID of the student in the DB', examples='P001')):
    # load all the data
    data = load_data()
    if student_id in data:
        return data[student_id]
    raise HTTPException(status_code=404, detail=f'student id {student_id} not found in the date')

#

# ------------- Query Parameter -------------
'''
Example:
/students?city=Delhi&sort_by=age

Syntax Rules:

- The ? marks the start of query parameters
- Each parameter is a key-value pair: key=value
- Multiple parameters are separated by &

In this example:

- city=Delhi is a query parameter for filtering students by city
- sort_by=age is a query parameter for sorting results by age
'''

# a query endpoint to get the data in sorted form in either asc or desc order
@app.get('/sort')
def sort_by_students(sort_by: str = Query(..., description='sort by age, height or bmi'), 
                     order: str = Query('asc', description='sort in ascending or descending order')):
    valid_sort_by = ['height', 'weight', 'bmi']

    if sort_by not in valid_sort_by:
        raise HTTPException(status_code=400, detail=f'Invalid sort value use one of {valid_sort_by}')
    if order not in ['asc', 'desc']:
        raise HTTPException(status_code=400, detail='invalid order use one of [asc, desc]')

    sort_order = True if 'asc' else False

    data = load_data()

    sorted_data = sorted(data.values(), key=lambda x: x.get(sort_by,0), reverse=sort_order)
    
    return sorted_data



# a post to method to create new Students
@app.post('/createStudent')
def createStudent(student: student):
    data = load_data()
    student_data = {}

    # model_dump is to unpack the object data into the data format
    student_data[student.id] = student.model_dump(exclude='id')

    if student.id in data: raise HTTPException(status_code=400, detail='student already exists')

    save_data(data)

    return JSONResponse(status_code=201, content='Patient created successfully')



# # a put method to update the existing Students
# @app.put('/update')
# def updateStudent(updatePatient: UpdateStudent): # need to create a new pydantic student class with optional values as not all the field are requierd
#     pass
