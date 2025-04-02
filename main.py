from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from passlib.context import CryptContext

# 1. 앱 객체 생성
app = FastAPI()

# 2. DB 연결
client = MongoClient("mongodb+srv://jegalhhh:1234@morning-cluster.rjlkphg.mongodb.net/?retryWrites=true&w=majority&appName=morning-cluster")
db = client["morning_db"]
users_collection = db["users"]

# 3. 비밀번호 암호화 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 4. 모델 정의
class UserSignup(BaseModel):
    phone: str
    name: str
    student_id: str
    department: str
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

# 5. 회원가입 API
@app.post("/signup")
def signup(user: UserSignup):
    if users_collection.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")

    hashed_pw = pwd_context.hash(user.password)
    user_dict = user.dict()
    user_dict["password"] = hashed_pw
    users_collection.insert_one(user_dict)

    return {"msg": "회원가입 성공!"}

# 6. 로그인 API
@app.post("/login")
def login(user: UserLogin):
    found = users_collection.find_one({"username": user.username})
    if not found:
        raise HTTPException(status_code=404, detail="존재하지 않는 아이디입니다.")

    if not pwd_context.verify(user.password, found["password"]):
        raise HTTPException(status_code=401, detail="비밀번호가 틀렸습니다.")

    return {"msg": "로그인 성공!"}
