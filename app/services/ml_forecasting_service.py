from sqlalchemy.orm import Session
from prophet import Prophet
import pandas as pd

class MLForecastingService:
    def __init__(self, db: Session):
        self.db = db
    
    def train_and_predict(self, months_ahead: int = 3):
        # 1. Obtener datos históricos
        historical = self._get_historical_data()
        
        # 2. Preparar datos para Prophet
        df = pd.DataFrame(historical)
        df = df.rename(columns={'date': 'ds', 'total': 'y'})
        
        # 3. Entrenar modelo
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False
        )
        model.fit(df)
        
        # 4. Hacer predicción
        future = model.make_future_dataframe(periods=months_ahead*30)
        forecast = model.predict(future)
        
        return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(months_ahead*30)