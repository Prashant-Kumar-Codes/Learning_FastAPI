from fastapi import FastAPI

# Path parameter class in fastapi
from fastapi import Path

# HTTP Exception class in fastapi for http status codes
from fastapi import HTTPException

import json


app = FastAPI()

# helper function

def load_data():
    with open('paitents.json', 'r') as f:
        data = json.load(f)
    
    return data

@app.get("/")
def welcome():
    return {'message':'Welcome to Patients Mangement System API'}

@app.get("/about")
def about():
    return {'message':'A fully functional API whose endpoint is /about'}

@app.get("/view")
def view():
    data = load_data()
    return data

# Path Parameter
'''The Path() function in FastAPI is used to provide metadata, validation rules, and documentation hints for path parameter in you API endpoints

Title
Description
Example
ge, gt, le, lt
Min_length
Max_length
Regex
'''

# to get the patient detials with paitent id
@app.get("/paitent/{paitent_id}")
def view_paitents_via_id(paitent_id: str = Path(..., description='ID of the paitent in the DB', example='P001')):
    # load all the data
    data = load_data()
    if paitent_id in data:
        return data[paitent_id]
    raise HTTPException(status_code=404, detail=f'paitent id {paitent_id} not found in the date')

#

