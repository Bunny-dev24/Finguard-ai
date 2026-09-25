from fastapi import APIRouter, Depends
from src.api.dependencies import get_alert_service
from src.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def open_alerts(limit: int = 50, svc: AlertService = Depends(get_alert_service)):
    return svc.list_open(limit)


@router.post("/{alert_id}/review")
def review_alert(alert_id: int, svc: AlertService = Depends(get_alert_service)):
    svc.review(alert_id)
    return {"status": "reviewed", "alert_id": alert_id}