from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.db.schemas import ChatQuery, ChatResponse
from backend.app.api.auth import get_current_user
from backend.app.services.open_ai import answer_chat_query

router = APIRouter(prefix="/chat", tags=["Security Assistant"])

@router.post("", response_model=ChatResponse)
def ask_assistant(payload: ChatQuery, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Submits a natural language query to the security chatbot.
    Queries active logs database metadata context dynamically to formulate technical tactical responses.
    """
    try:
        ans_data = answer_chat_query(payload.message, db)
        return ChatResponse(
            response=ans_data["response"],
            suggested_commands=ans_data.get("suggested_commands", [])
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Security Assistant intelligence module error: {str(e)}"
        )
