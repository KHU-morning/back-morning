from pymongo import MongoClient

# 복사한 URI로 아래 client 생성 (너의 URI로 바꿨지?)
client = MongoClient("mongodb+srv://jegalhhh:1234@morning-cluster.rjlkphg.mongodb.net/?retryWrites=true&w=majority&appName=morning-cluster")

# 사용할 데이터베이스 이름
db = client["morning_db"]

# 사용자 정보를 저장할 컬렉션
users_collection = db["users"]
