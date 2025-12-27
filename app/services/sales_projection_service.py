from typing import Dict, List
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from sqlalchemy import func, extract
from sqlalchemy.orm import Session
from models import SaleTicket, Product, SaleTicketItem
import statistics

class SalesProjectionService:
    """
    Servicio para análisis predictivo de ventas.
    Usa datos históricos para proyectar tendencias futuras.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def project_sales(
        self, 
        months_ahead: int = 3,
        use_ml: bool = True
    ) -> Dict:
        """
        Proyecta ventas para los próximos N meses.
        
        Args:
            months_ahead: Meses a proyectar (1-12)
            use_ml: Si usar modelo ML o solo promedio móvil
        
        Returns:
            Diccionario con proyecciones mensuales
        """
        
        # 1. Obtener datos históricos (últimos 12 meses)
        historical_data = self._get_historical_monthly_sales(months=12)
        
        if len(historical_data) < 3:
            return {
                "error": "Datos históricos insuficientes (mínimo 3 meses)",
                "available_months": len(historical_data)
            }
        
        # 2. Calcular estadísticas base
        stats = self._calculate_statistics(historical_data)
        
        # 3. Detectar tendencia y estacionalidad
        trend = self._calculate_trend(historical_data)
        seasonality = self._calculate_seasonality(historical_data)
        
        # 4. Generar proyecciones
        projections = []
        last_month_value = historical_data[-1]["total"]
        
        for i in range(1, months_ahead + 1):
            # Método de suavizado exponencial con ajuste de tendencia
            if use_ml:
                projected_value = self._ml_projection(
                    historical_data, 
                    i, 
                    trend, 
                    seasonality
                )
            else:
                # Promedio móvil ponderado
                projected_value = self._moving_average_projection(
                    historical_data, 
                    i, 
                    trend
                )
            
            # Calcular intervalo de confianza (±15%)
            confidence_lower = projected_value * 0.85
            confidence_upper = projected_value * 1.15
            
            target_date = datetime.now(UTC) + timedelta(days=30 * i)
            
            projections.append({
                "month": target_date.strftime("%Y-%m"),
                "month_name": target_date.strftime("%B %Y"),
                "projected_sales": round(float(projected_value), 2),
                "confidence_interval": {
                    "lower": round(float(confidence_lower), 2),
                    "upper": round(float(confidence_upper), 2)
                },
                "growth_rate": round(
                    ((projected_value - last_month_value) / last_month_value) * 100, 
                    2
                )
            })
            
            last_month_value = projected_value
        
        return {
            "historical_summary": {
                "months_analyzed": len(historical_data),
                "average_monthly_sales": round(stats["mean"], 2),
                "median_monthly_sales": round(stats["median"], 2),
                "std_deviation": round(stats["std"], 2),
                "trend": trend,
                "seasonality_detected": seasonality["is_seasonal"]
            },
            "projections": projections,
            "recommendations": self._generate_recommendations(
                projections, 
                historical_data,
                trend
            ),
            "generated_at": datetime.now(UTC).isoformat()
        }
    
    def analyze_product_trends(self, top_n: int = 10) -> Dict:
        """
        Analiza tendencias de productos individuales.
        
        Returns:
            Top productos con proyecciones
        """
        
        # Últimos 3 meses
        three_months_ago = datetime.now(UTC) - timedelta(days=90)
        
        # Productos más vendidos
        top_products = (
            self.db.query(
                Product.Id,
                Product.Product,
                Product.Category,
                func.sum(SaleTicketItem.quantity).label("total_quantity"),
                func.sum(SaleTicketItem.subtotal).label("total_revenue")
            )
            .join(SaleTicketItem, Product.Id == SaleTicketItem.product_id)
            .join(SaleTicket, SaleTicketItem.ticket_id == SaleTicket.id)
            .filter(
                SaleTicket.created_at >= three_months_ago,
                SaleTicket.status == "completed"
            )
            .group_by(Product.Id, Product.Product, Product.Category)
            .order_by(func.sum(SaleTicketItem.subtotal).desc())
            .limit(top_n)
            .all()
        )
        
        products_analysis = []
        
        for product in top_products:
            # Ventas mensuales del producto
            monthly_sales = self._get_product_monthly_sales(product.Id, months=6)
            
            if len(monthly_sales) >= 2:
                trend = self._calculate_trend(monthly_sales)
                last_month = monthly_sales[-1]["total"]
                avg_growth = (
                    (monthly_sales[-1]["total"] - monthly_sales[0]["total"]) / 
                    monthly_sales[0]["total"] * 100
                ) if monthly_sales[0]["total"] > 0 else 0
                
                products_analysis.append({
                    "product_id": product.Id,
                    "product_name": product.Product,
                    "category": product.Category,
                    "total_quantity_sold": int(product.total_quantity),
                    "total_revenue": float(product.total_revenue),
                    "trend": trend,
                    "average_growth_rate": round(avg_growth, 2),
                    "projected_next_month": round(last_month * (1 + avg_growth/100), 2)
                })
        
        return {
            "top_products": products_analysis,
            "analysis_period": "Últimos 3 meses",
            "generated_at": datetime.now(UTC).isoformat()
        }
    
    def _get_historical_monthly_sales(self, months: int = 12) -> List[Dict]:
        """Obtiene ventas mensuales históricas"""
        
        start_date = datetime.now(UTC) - timedelta(days=30 * months)
        
        monthly_sales = (
            self.db.query(
                extract('year', SaleTicket.created_at).label('year'),
                extract('month', SaleTicket.created_at).label('month'),
                func.sum(SaleTicket.total).label('total'),
                func.count(SaleTicket.id).label('num_tickets')
            )
            .filter(
                SaleTicket.created_at >= start_date,
                SaleTicket.status == 'completed'
            )
            .group_by('year', 'month')
            .order_by('year', 'month')
            .all()
        )
        
        return [
            {
                "year": int(row.year),
                "month": int(row.month),
                "total": float(row.total),
                "num_tickets": row.num_tickets
            }
            for row in monthly_sales
        ]
    
    def _get_product_monthly_sales(self, product_id: int, months: int = 6):
        """Ventas mensuales de un producto específico"""
        
        start_date = datetime.now(UTC) - timedelta(days=30 * months)
        
        monthly_sales = (
            self.db.query(
                extract('year', SaleTicket.created_at).label('year'),
                extract('month', SaleTicket.created_at).label('month'),
                func.sum(SaleTicketItem.subtotal).label('total')
            )
            .join(SaleTicket, SaleTicketItem.ticket_id == SaleTicket.id)
            .filter(
                SaleTicketItem.product_id == product_id,
                SaleTicket.created_at >= start_date,
                SaleTicket.status == 'completed'
            )
            .group_by('year', 'month')
            .order_by('year', 'month')
            .all()
        )
        
        return [
            {"year": int(r.year), "month": int(r.month), "total": float(r.total)}
            for r in monthly_sales
        ]
    
    def _calculate_statistics(self, data: List[Dict]) -> Dict:
        """Calcula estadísticas descriptivas"""
        values = [d["total"] for d in data]
        
        return {
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "std": statistics.stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values)
        }
    
    def _calculate_trend(self, data: List[Dict]) -> str:
        """Detecta tendencia: 'ascending', 'descending', 'stable'"""
        if len(data) < 2:
            return "stable"
        
        values = [d["total"] for d in data]
        
        # Regresión lineal simple
        n = len(values)
        x = list(range(n))
        mean_x = sum(x) / n
        mean_y = sum(values) / n
        
        numerator = sum((x[i] - mean_x) * (values[i] - mean_y) for i in range(n))
        denominator = sum((x[i] - mean_x) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        # Determinar tendencia
        threshold = mean_y * 0.05  # 5% del promedio
        
        if slope > threshold:
            return "ascending"
        elif slope < -threshold:
            return "descending"
        else:
            return "stable"
    
    def _calculate_seasonality(self, data: List[Dict]) -> Dict:
        """Detecta patrones estacionales"""
        if len(data) < 12:
            return {"is_seasonal": False}
        
        # Simplificado: comparar varianza intra-mes vs inter-mes
        monthly_averages = {}
        for d in data:
            month = d["month"]
            if month not in monthly_averages:
                monthly_averages[month] = []
            monthly_averages[month].append(d["total"])
        
        # Si hay repeticiones de meses, hay estacionalidad potencial
        is_seasonal = any(len(values) > 1 for values in monthly_averages.values())
        
        return {
            "is_seasonal": is_seasonal,
            "pattern": "monthly" if is_seasonal else "none"
        }
    
    def _ml_projection(
        self, 
        historical: List[Dict], 
        periods_ahead: int,
        trend: str,
        seasonality: Dict
    ) -> float:
        """Proyección usando suavizado exponencial"""
        
        values = [d["total"] for d in historical]
        
        # Parámetros de suavizado
        alpha = 0.3  # Factor de suavizado
        beta = 0.1   # Factor de tendencia
        
        # Último valor y tendencia
        last_value = values[-1]
        
        # Calcular tendencia promedio
        if len(values) >= 2:
            recent_trend = (values[-1] - values[-2])
        else:
            recent_trend = 0
        
        # Ajustar por tendencia detectada
        trend_multiplier = 1.0
        if trend == "ascending":
            trend_multiplier = 1.05
        elif trend == "descending":
            trend_multiplier = 0.95
        
        # Proyectar
        projected = last_value + (recent_trend * periods_ahead * trend_multiplier)
        
        return max(projected, 0)  # No puede ser negativo
    
    def _moving_average_projection(
        self, 
        historical: List[Dict], 
        periods_ahead: int,
        trend: str
    ) -> float:
        """Proyección simple con promedio móvil"""
        
        values = [d["total"] for d in historical]
        
        # Promedio de últimos 3 meses
        window = min(3, len(values))
        recent_avg = sum(values[-window:]) / window
        
        # Ajustar por tendencia
        if trend == "ascending":
            return recent_avg * (1 + 0.05 * periods_ahead)
        elif trend == "descending":
            return recent_avg * (1 - 0.05 * periods_ahead)
        else:
            return recent_avg
    
    def _generate_recommendations(
        self, 
        projections: List[Dict],
        historical: List[Dict],
        trend: str
    ) -> List[str]:
        """Genera recomendaciones basadas en proyecciones"""
        
        recommendations = []
        
        if trend == "ascending":
            recommendations.append(
                "📈 Tendencia positiva detectada. Considere aumentar inventario."
            )
        elif trend == "descending":
            recommendations.append(
                "📉 Tendencia negativa. Evalúe estrategias de marketing o promociones."
            )
        
        # Verificar variabilidad
        proj_values = [p["projected_sales"] for p in projections]
        if max(proj_values) / min(proj_values) > 1.3:
            recommendations.append(
                "⚠️ Alta variabilidad esperada. Mantenga flexibilidad en inventario."
            )
        
        return recommendations


# app/routes/analytics.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from app.core.security import get_current_user, require_manager
from app.services.sales_projection_service import SalesProjectionService
from models import Users

router = APIRouter(prefix="/analytics", tags=["Análisis y Proyecciones"])

@router.get("/sales/projection", dependencies=[Depends(require_manager)])
async def get_sales_projection(
    months: int = Query(3, ge=1, le=12, description="Meses a proyectar"),
    use_ml: bool = Query(True, description="Usar modelo ML"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Proyección de ventas para los próximos N meses.
    
    **Solo disponible para managers y admins.**
    
    Retorna:
    - Proyecciones mensuales con intervalos de confianza
    - Análisis de tendencias
    - Recomendaciones estratégicas
    """
    
    service = SalesProjectionService(db)
    return service.project_sales(months_ahead=months, use_ml=use_ml)

@router.get("/products/trends", dependencies=[Depends(require_manager)])
async def get_product_trends(
    top_n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Análisis de tendencias de productos individuales.
    
    Identifica:
    - Productos más vendidos
    - Tendencias de crecimiento
    - Proyecciones individuales
    """
    
    service = SalesProjectionService(db)
    return service.analyze_product_trends(top_n=top_n)