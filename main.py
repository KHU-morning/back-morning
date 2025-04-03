from fastapi import FastAPI, HTTPException, Depends, Path, Query
from pydantic import BaseModel
from pymongo import MongoClient
from passlib.context import CryptContext
from pydantic import BaseModel
from uuid import uuid4
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
import json
from typing import List
import pytz
from agora_token_builder import RtcTokenBuilder


# 앱 생성
app = FastAPI()

# JWT 관련 상수 및 암호화 설정
SECRET_KEY = "super-secret-kyunghee-morning123!"  # 실제 서비스에서는 환경변수로 관리
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# OAuth2 설정 
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 비밀번호 암호화 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# MongoDB Atlas 클러스터 연결
client = MongoClient("mongodb+srv://jegalhhh:1234@morning-cluster.rjlkphg.mongodb.net/?retryWrites=true&w=majority&appName=morning-cluster")
db = client["morning_db"]

# 컬렉션 정의
users_collection = db["users"]
rooms_collection = db["morning_rooms"]
wake_records_collection = db["wake_records"]
wake_requests_collection = db["wake_requests"]
ratings_collection = db["wake_ratings"]



# JWT 토큰 생성 함수
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# access_token으로 현재 로그인한 사용자 정보를 가져오는 함수
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="인증 정보가 유효하지 않습니다.",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = users_collection.find_one({"username": username})
    if user is None:
        raise credentials_exception

    return user

# 회원가입 요청용
class UserSignup(BaseModel):
    phone: str
    name: str
    student_id: str
    department: str
    username: str
    password: str

# 로그인 요청용 (현재 미사용, Swagger 내 form 방식으로 대체)
class UserLogin(BaseModel):
    username: str
    password: str

# 모닝방 생성 요청용
class RoomCreate(BaseModel):
    title: str
    wake_date: str  # "2025-04-07"
    wake_time: str  # "08:30"
    is_private: bool

# 모닝방 채팅용
class ChatMessage(BaseModel):
    type: str  # "chat"
    username: str
    name: str
    message: str
    timestamp: str


# (현재 미사용) 모닝방 참여 요청용
class JoinRoomRequest(BaseModel):
    username: str

# 마이페이지 기상 기록
class WakeRecord(BaseModel):
    date: str            # 날짜: "2025-04-03"
    success: bool        # 성공 여부: True or False
    type: str            # "모닝방" / "모닝콜" / "혼자 기상"
    wake_time: str       # 목표 기상 시간: "08:00"
    reason: str          # 기상 이유: 자유 텍스트
    participants: List[str]  # 함께한 사람들 ID 리스트

# 모닝콜 요청
class WakeRequestCreate(BaseModel):
    wake_date: str         # "2025-04-07"
    wake_time: str         # "08:30"
    reason: str            # 이유
    is_public: bool        # 공개 여부 (true/false)

# 모닝콜 요청 리스트
class WakeRequest(BaseModel):
    request_id: str
    requester: str
    wake_date: str
    wake_time: str
    reason: str
    is_public: bool
    accepted_by: str | None = None
    status: str = "open"  # open, accepted, done
    created_at: str

# 평가 요청 모델
class RatingRequest(BaseModel):
    request_id: str  # 평가할 모닝콜 요청 ID
    to: str          # 평가 대상 유저 username
    result: str      # "like" or "dislike"

# 회원가입 API
# 회원가입 정보 (username, password 등)를 받아 DB에 저장
@app.post("/signup")
def signup(user: UserSignup):
    if users_collection.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")

    hashed_pw = pwd_context.hash(user.password)
    user_dict = user.dict()
    user_dict["password"] = hashed_pw
    users_collection.insert_one(user_dict)

    return {"msg": "회원가입 성공!"}

# JWT 토큰 발급용 로그인 API
# 클라이언트는 이 API를 통해 access_token을 발급받아야 함
@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_collection.find_one({"username": form_data.username})
    if not user or not pwd_context.verify(form_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호 오류")

    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


# 마이페이지 조회 API (로그인 필요)
# access_token으로 로그인한 사용자의 정보(username, 학과, 평판, 프로필사진 등)를 반환
@app.get("/me")
def get_my_profile(user: dict = Depends(get_current_user)):
    return {
        "username": user["username"],
        "name": user["name"],
        "department": user["department"],
        "reputation": user.get("reputation", 0),
        "profile_image": user.get("profile_image", "")
    }



# 모닝방 생성 API (로그인 필요)
# 로그인한 사용자가 모닝방을 생성함. 방 제목, 날짜, 시간, 공개 여부 입력
@app.post("/rooms")
def create_room(room: RoomCreate, user: dict = Depends(get_current_user)):
    room_id = str(uuid4())[:8]
    room_data = room.dict()
    room_data.update({
        "room_id": room_id,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": user["username"],  
        "participants": [user["username"]]
    })

    rooms_collection.insert_one(room_data)
    return {"msg": "모닝방이 생성되었습니다!", "room_id": room_id}


# 공개된 모닝방 리스트 조회 API (로그인 불필요)
# 공개방만 정렬하여 리스트로 반환.
@app.get("/rooms")
def list_public_rooms():
    rooms = list(rooms_collection.find({"is_private": False}).sort("wake_date", 1))
    
    result = []
    for room in rooms:
        result.append({
            "room_id": room["room_id"],
            "title": room["title"],  
            "created_by": room["created_by"],
            "wake_date": room["wake_date"],
            "wake_time": room["wake_time"]
        })

    return result


# 모닝방 상세 정보 조회 API (로그인 불필요)
# room_id를 통해 방 상세 정보 확인
@app.get("/rooms/{room_id}")
def get_room_detail(room_id: str = Path(...)):
    room = rooms_collection.find_one({"room_id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="모닝방을 찾을 수 없습니다.")

    # ⏱ 기상 시간 계산 (이전 코드 그대로 유지)
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst)
    try:
        target_dt = kst.localize(datetime.strptime(f"{room['wake_date']} {room['wake_time']}", "%Y-%m-%d %H:%M"))
        diff = target_dt - now
        minutes_left = int(diff.total_seconds() // 60)

        if minutes_left > 0:
            time_left = f"{minutes_left}분 후"
        elif -10 <= minutes_left <= 0:
            time_left = "기상 시간!"
        else:
            time_left = "기상 시간 지남"
    except:
        time_left = "시간 계산 오류"

    # 👥 참가자 상세 정보 가져오기
    participant_infos = []
    for username in room.get("participants", []):
        user = users_collection.find_one({"username": username})
        if user:
            participant_infos.append({
                "username": user["username"],
                "name": user["name"],
                "department": user["department"],
                "profile_image": user.get("profile_image", "")
            })

    return {
        "room_id": room["room_id"],
        "title": room["title"],
        "created_by": room["created_by"],
        "wake_date": room["wake_date"],
        "wake_time": room["wake_time"],
        "is_private": room["is_private"],
        "time_left": time_left,
        "participants": participant_infos 
    }



# 모닝방 참여하기 API (로그인 필요)
# 로그인한 사용자가 특정 room_id의 모닝방에 참여 (중복 참여 방지)
@app.post("/rooms/{room_id}/join")
def join_room(room_id: str, user: dict = Depends(get_current_user)):
    room = rooms_collection.find_one({"room_id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="모닝방을 찾을 수 없습니다.")

    username = user["username"]

    if username in room.get("participants", []):
        return {"msg": "이미 참여한 사용자입니다.", "participants": room["participants"]}

    rooms_collection.update_one(
        {"room_id": room_id},
        {"$push": {"participants": username}}
    )

    updated_room = rooms_collection.find_one({"room_id": room_id})
    return {"msg": "참여 완료!", "participants": updated_room["participants"]}


# 방별 연결 사용자 저장소
room_connections = {}

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    async def disconnect(self, room_id: str, websocket: WebSocket):
        self.active_connections[room_id].remove(websocket)

    async def broadcast(self, room_id: str, message: str):
        for connection in self.active_connections.get(room_id, []):
            await connection.send_text(message)


manager = ConnectionManager()


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    kst = pytz.timezone("Asia/Seoul")
    await websocket.accept()

    # 🔐 username을 query로 전달받기 (예: /ws/abcd1234?username=hgd123)
    username = websocket.query_params.get("username")

    user = users_collection.find_one({"username": username})
    name = user["name"] if user else "알 수 없음"

    await manager.connect(room_id, websocket)

    # 👉 입장 메시지 전송
    join_msg = {
        "type": "system",
        "message": f"{name}({username}) 님이 입장했습니다 👋",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    await manager.broadcast(room_id, json.dumps(join_msg))

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)

            # 프로필 이미지 추가
            if user:
                data["profile_image"] = user.get("profile_image", "")

            data["timestamp"] = datetime.now(kst).strftime("%Y-%m-%d %H:%M")
            await manager.broadcast(room_id, json.dumps(data))

    except WebSocketDisconnect:
        await manager.disconnect(room_id, websocket)

        # 👉 퇴장 메시지 전송
        leave_msg = {
            "type": "system",
            "message": f"{name}({username}) 님이 퇴장했습니다 👋",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        await manager.broadcast(room_id, json.dumps(leave_msg))



# 날짜별 기록 조회 API (달력 눌렀을 때)
@app.get("/me/wake-record/{date}")
def get_wake_record(date: str, user: dict = Depends(get_current_user)):
    record = wake_records_collection.find_one({"username": user["username"], "date": date})
    if not record:
        raise HTTPException(status_code=404, detail="기상 기록이 없습니다.")
    
    return {
        "date": record["date"],
        "success": record["success"],
        "type": record["type"],
        "wake_time": record["wake_time"],
        "reason": record["reason"],
        "participants": record.get("participants", [])
    }

# 날짜별 기록 조회 API (달력 색칠용)
@app.get("/me/wake-records")
def get_wake_summary(user: dict = Depends(get_current_user)):
    records = list(wake_records_collection.find({"username": user["username"]}))
    
    return [
        {"date": rec["date"], "success": rec["success"]}
        for rec in records
    ]

# 모닝콜 요청 게시 API
@app.post("/wake-requests")
def create_wake_request(req: WakeRequestCreate, user: dict = Depends(get_current_user)):
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst)

    request_data = WakeRequest(
        request_id=str(uuid4())[:8],
        requester=user["username"],
        wake_date=req.wake_date,
        wake_time=req.wake_time,
        reason=req.reason,
        is_public=req.is_public,
        created_at=now.isoformat()
    ).dict()

    wake_requests_collection.insert_one(request_data)
    return {"msg": "모닝콜 요청 등록 완료!", "request_id": request_data["request_id"]}


# 모닝콜 요청 리스트 조회 API
@app.get("/wake-requests")
def list_wake_requests(user: dict = Depends(get_current_user)):
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst)

    # 상태 관계없이 전체 요청 가져오기
    requests = list(wake_requests_collection.find().sort("wake_date", 1))

    result = []
    for req in requests:
        # ⏱ 유효기간 지난 "open" 요청 자동 만료 처리
        wake_dt = kst.localize(datetime.strptime(f"{req['wake_date']} {req['wake_time']}", "%Y-%m-%d %H:%M"))
        if now > wake_dt and req["status"] == "open":
            wake_requests_collection.update_one(
                {"request_id": req["request_id"]},
                {"$set": {"status": "expired"}}
            )
            req["status"] = "expired"

        # 프론트가 보기 쉽게 open 상태만 보여주기
        if req["status"] != "open":
            continue

        # reason 공개 여부 처리
        reason = (
            req["reason"] if req["is_public"] or req["requester"] == user["username"]
            else "비공개"
        )

        result.append({
            "request_id": req["request_id"],
            "requester": req["requester"],
            "wake_date": req["wake_date"],
            "wake_time": req["wake_time"],
            "reason": reason,
            "is_public": req["is_public"],
            "accepted_by": req.get("accepted_by"),
            "status": req["status"]
        })

    return result


# 모닝콜 요청 수락 API
@app.post("/wake-requests/{request_id}/accept")
def accept_wake_request(request_id: str, user: dict = Depends(get_current_user)):
    req = wake_requests_collection.find_one({"request_id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")

    if req["status"] != "open":
        raise HTTPException(status_code=400, detail="이미 수락된 요청입니다.")

    if req["requester"] == user["username"]:
        raise HTTPException(status_code=400, detail="자기 자신의 요청은 수락할 수 없습니다.")

    wake_requests_collection.update_one(
        {"request_id": request_id},
        {
            "$set": {
                "accepted_by": user["username"],
                "status": "accepted"
            }
        }
    )

    return {"msg": "모닝콜 요청을 수락했습니다!"}

# 내가 요청하거나 수락한 모닝콜 상세정보 API
@app.get("/wake-requests/{request_id}")
def get_wake_request_detail(request_id: str, user: dict = Depends(get_current_user)):
    req = wake_requests_collection.find_one({"request_id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")

    # 요청자 또는 수락자만 접근 가능
    if req["requester"] != user["username"] and req.get("accepted_by") != user["username"]:
        raise HTTPException(status_code=403, detail="해당 요청에 접근할 수 없습니다.")

    # 기상 대상 정보 가져오기 (무조건 requester)
    target_user = users_collection.find_one({"username": req["requester"]})
    target_info = {
        "username": target_user["username"],
        "name": target_user["name"],
        "profile_image": target_user.get("profile_image", "")
    } if target_user else None

    return {
        "wake_date": req["wake_date"],
        "wake_time": req["wake_time"],
        "status": req["status"],
        "reason": req["reason"],
        "target": target_info,  # 👈 프론트에선 "기상 대상"으로 사용
        "you_are_helper": user["username"] == req.get("accepted_by")
    }


# 전화 성공 실패 여부 저장 API
@app.post("/wake-requests/{request_id}/result")
def record_wake_result(
    request_id: str,
    success: bool = Query(...),
    user: dict = Depends(get_current_user)
):
    req = wake_requests_collection.find_one({"request_id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")

    # 수락자 본인만 기록 가능
    if req.get("accepted_by") != user["username"]:
        raise HTTPException(status_code=403, detail="기록 권한이 없습니다.")

    # 중복 저장 방지
    if req.get("wake_recorded"):
        raise HTTPException(status_code=400, detail="이미 기상 기록이 저장되었습니다.")

    # 요청자 정보 가져오기
    requester = users_collection.find_one({"username": req["requester"]})
    if not requester:
        raise HTTPException(status_code=404, detail="요청자 정보를 찾을 수 없습니다.")

    # wake_records 저장
    wake_records_collection.update_one(
        {"username": requester["username"], "date": req["wake_date"]},
        {
            "$set": {
                "username": requester["username"],
                "date": req["wake_date"],
                "success": success,
                "type": "모닝콜",
                "wake_time": req["wake_time"],
                "reason": req["reason"],
                "participants": [user["username"]]
            }
        },
        upsert=True
    )

    # 상태 표시
    wake_requests_collection.update_one(
        {"request_id": request_id},
        {"$set": {"wake_recorded": True}}
    )

    return {
        "msg": "기상 기록 저장 완료!",
        "success": success
    }



# Agora 설정 (환경변수로 빼도 좋음)
AGORA_APP_ID = "154f7e38672c4cc2b51520502ace336f"
AGORA_APP_CERTIFICATE = "9ce097af561b44b2a571d632416ad008"

# Agora Token 발급 API
@app.get("/agora/token")
def get_agora_token(channel_name: str, user_id: int, user: dict = Depends(get_current_user)):
    expire_time_seconds = 3600  # 토큰 유효시간: 1시간
    current_timestamp = int(datetime.utcnow().timestamp())
    privilege_expired_ts = current_timestamp + expire_time_seconds

    token = RtcTokenBuilder.buildTokenWithUid(
        AGORA_APP_ID,
        AGORA_APP_CERTIFICATE,
        channel_name,
        user_id,  # 반드시 int
        1,  # Role: publisher
        privilege_expired_ts
    )

    return {
        "appId": AGORA_APP_ID,
        "channelName": channel_name,
        "uid": user_id,
        "token": token
    }


# 평판 평가 API
@app.post("/rate")
def rate_user(rating: RatingRequest, user: dict = Depends(get_current_user)):
    from_username = user["username"]
    to_username = rating.to

    # 중복 평가 방지
    existing = ratings_collection.find_one({
        "request_id": rating.request_id,
        "from": from_username
    })

    if existing:
        raise HTTPException(400, "이미 평가한 요청입니다.")

    # 평판 점수 반영
    delta = 1 if rating.result == "like" else -1

    users_collection.update_one(
        {"username": to_username},
        {"$inc": {"reputation": delta}}
    )

    # 평가 기록 저장
    ratings_collection.insert_one({
        "request_id": rating.request_id,
        "from": from_username,
        "to": to_username,
        "result": rating.result,
        "timestamp": datetime.now().isoformat()
    })

    return {"msg": "평가 완료!"}
