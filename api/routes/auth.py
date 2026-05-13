from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database.models import User
from auth.jwt_utils import get_password_hash, verify_password, create_access_token
from auth.rbac import get_current_user
from database.session import get_db
from api.schemas import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter()

@router.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_pw = get_password_hash(request.password)
    new_user = User(username=request.username, hashed_password=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"id": new_user.id, "username": new_user.username, "role": new_user.role}

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me")
def get_me(current_user=Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role}
