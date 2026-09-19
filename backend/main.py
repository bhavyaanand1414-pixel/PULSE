from fastapi import FastAPI
app=FastAPI(title="PULSE API")
@app.get("/")
def root():
    #root is the function that will be called whenever get is sent 
    #Whenever someone sends GET /, execute the root() function.
    return {
        "message":"PULSE API is running"
    }
@app.get("/health")
def health_check():
    return {
        "status":"healthy",
        "service": "PULSE API"
    }   