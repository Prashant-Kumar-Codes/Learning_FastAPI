from fastapi import FastAPI
import json

app = FastAPI()

@app.get("/")
def welcome():
    return {'message':'Welcome to Patients Mangement System API'}

@app.get("/about")
def about():
    return {'message':'A fully functional API whose endpoint is /about'}
