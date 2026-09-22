from fastapi import FastAPI
import json

# Path parameter class in fastapi
from fastapi import Path

# HTTP Exception class in fastapi for http status codes
from fastapi import HTTPException

# Query class from fastapi for query endpoints
from fastapi import Query

# import BaseModel class from Pydantic for data validation
from pydantic import BaseModel


app = FastAPI()

# helper function

def load_data():
    with open('paitents.json', 'r') as f:
        data = json.load(f)
    return data

class Paitent(BaseModel):
    name: str
    city: str
    age: int
    gender: str
    height: float
    weight: float

    


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
def view_paitents_via_id(paitent_id: str = Path(..., description='ID of the paitent in the DB', examples='P001')):
    # load all the data
    data = load_data()
    if paitent_id in data:
        return data[paitent_id]
    raise HTTPException(status_code=404, detail=f'paitent id {paitent_id} not found in the date')

#

# ------------- Query Parameter -------------
'''
Query parameters: are optional key-value pairs appended to the end of a URL, used to pass additional data to the server in an HTTP request. They are typically employed for operations like filtering, sorting, searching, and pagination without altering the endpoint path itself.

Example:
/patients?city=Delhi&sort_by=age

Syntax Rules:

- The ? marks the start of query parameters
- Each parameter is a key-value pair: key=value
- Multiple parameters are separated by &

In this example:

- city=Delhi is a query parameter for filtering patients by city
- sort_by=age is a query parameter for sorting results by age

Key Points:

- Query parameters do not change the endpoint path
- They customize the response based on specific criteria
- Common uses include filtering, sorting, searching, and pagination
- Multiple parameters are combined using the & symbol
- Special characters in parameter values should be URL-encoded (e.g., spaces become %20)


Query() is a utility function provided by FastAPI to declare, validate, and document query parameters in
your API endpoints.
'''

# a query endpoint to get the data in sorted form in either asc or desc order
@app.get('/sort')
def sort_by_paitents(sort_by: str = Query(..., description='sort by age, height or bmi'), 
                     order: str = Query('asc', description='sort in ascending or descending order')):
    valid_sort_by = ['height', 'weight', 'bmi']

    if sort_by not in valid_sort_by:
        raise HTTPException(status_code=400, detials=f'Invalid sort value use one of {valid_sort_by}')
    if order not in ['asc', 'desc']:
        raise HTTPException(status_code=400, detials='invalid order use one of [asc, desc]')

    sort_order = True if 'asc' else False

    data = load_data()

    sorted_data = sorted(data.values(), key=lambda x: x.get(sort_by,0), reverse=sort_order)
    
    return sorted_data
