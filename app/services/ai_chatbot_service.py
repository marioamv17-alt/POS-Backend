from typing import List, Dict
from datetime import datetime, UTC
import httpx
from sqlalchemy.orm import Session
from models import Product, Cart
from app.core.config import get_settings

settings = get_settings()

class ChatbotService:
    """
    Servicio de chatbot IA para soporte y ventas.
    Usa Claude API para procesamiento de lenguaje natural.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.model = "claude-sonnet-4-20250514"
    
    async def process_message(
        self, 
        user_message: str, 
        conversation_history: List[Dict] = None,
        user_id: int = None
    ) -> Dict:
        """
        Procesa un mensaje del usuario y genera respuesta inteligente.
        
        Args:
            user_message: Pregunta o comando del usuario
            conversation_history: Historial de conversación
            user_id: ID del usuario (opcional)
        
        Returns:
            Dict con respuesta y acciones sugeridas
        """
        
        # Construir contexto del negocio
        business_context = await self._get_business_context()
        
        # Construir el prompt del sistema
        system_prompt = f"""Eres un asistente virtual experto en ventas para un sistema POS.

INFORMACIÓN DEL NEGOCIO:
{business_context}

TUS CAPACIDADES:
1. Responder preguntas sobre productos disponibles
2. Ayudar a buscar productos por nombre, categoría o características
3. Sugerir productos relacionados o alternativos
4. Explicar precios, descuentos y ofertas
5. Guiar al usuario en el proceso de compra
6. Resolver dudas sobre stock disponible

REGLAS:
- Sé conciso pero amigable
- Usa lenguaje natural y profesional
- Si no tienes información, di que consultarás con un humano
- Sugiere productos similares cuando algo no está disponible
- Siempre verifica stock antes de recomendar

FORMATO DE RESPUESTA:
Responde en JSON con esta estructura:
{{
    "message": "Tu respuesta al usuario",
    "suggested_products": ["id1", "id2"],  // Si aplica
    "actions": ["add_to_cart", "search_product"],  // Acciones sugeridas
    "needs_human": false  // Si requiere intervención humana
}}"""
        
        # Preparar mensajes
        messages = []
        
        # Agregar historial si existe
        if conversation_history:
            messages.extend(conversation_history)
        
        # Agregar mensaje actual del usuario
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Llamar a Claude API
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Content-Type": "application/json",
                        "anthropic-version": "2023-06-01"
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 1000,
                        "system": system_prompt,
                        "messages": messages
                    }
                )
                
                if response.status_code != 200:
                    return self._fallback_response(user_message)
                
                result = response.json()
                ai_response = result["content"][0]["text"]
                
                # Parsear respuesta JSON de Claude
                import json
                try:
                    parsed_response = json.loads(ai_response)
                except json.JSONDecodeError:
                    # Si Claude no respondió en JSON, usar respuesta directa
                    parsed_response = {
                        "message": ai_response,
                        "suggested_products": [],
                        "actions": [],
                        "needs_human": False
                    }
                
                # Enriquecer con datos reales de productos
                if parsed_response.get("suggested_products"):
                    parsed_response["products"] = await self._get_products_details(
                        parsed_response["suggested_products"]
                    )
                
                return parsed_response
                
        except Exception as e:
            print(f"Error en chatbot: {e}")
            return self._fallback_response(user_message)
    
    async def _get_business_context(self) -> str:
        """Obtiene contexto del negocio para el chatbot"""
        
        # Top 10 productos más vendidos (simplificado)
        popular_products = self.db.query(Product).filter(
            Product.Activo == 1
        ).limit(10).all()
        
        # Resumen de inventario
        total_products = self.db.query(Product).filter(Product.Activo == 1).count()
        categories = self.db.query(Product.Category).distinct().all()
        
        context = f"""
- Total de productos disponibles: {total_products}
- Categorías: {', '.join([c[0] for c in categories])}
- Productos destacados: {', '.join([p.Product for p in popular_products[:5]])}
- Métodos de pago aceptados: Efectivo, Tarjeta, Transferencia
"""
        return context
    
    async def _get_products_details(self, product_ids: List[str]) -> List[Dict]:
        """Obtiene detalles de productos por IDs"""
        try:
            ids = [int(pid) for pid in product_ids]
            products = self.db.query(Product).filter(
                Product.Id.in_(ids),
                Product.Activo == 1
            ).all()
            
            return [
                {
                    "id": p.Id,
                    "name": p.Product,
                    "price": float(p.Price),
                    "stock": int(p.Stock),
                    "category": p.Category
                }
                for p in products
            ]
        except:
            return []
    
    def _fallback_response(self, user_message: str) -> Dict:
        """Respuesta de respaldo en caso de error"""
        return {
            "message": "Disculpa, estoy teniendo problemas técnicos. ¿Puedo ayudarte con algo específico como buscar un producto o verificar precios?",
            "suggested_products": [],
            "actions": [],
            "needs_human": True
        }


# app/routes/chatbot.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from pydantic import BaseModel
from typing import List, Dict
from app.services.ai_chatbot_service import ChatbotService

router = APIRouter(prefix="/chatbot", tags=["Chatbot IA"])

class ChatMessage(BaseModel):
    message: str
    conversation_id: str | None = None
    conversation_history: List[Dict] = []

class ChatResponse(BaseModel):
    response: str
    suggested_products: List[Dict] = []
    actions: List[str] = []
    conversation_id: str

# Almacenamiento temporal de conversaciones (usar Redis en producción)
conversations = {}

@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatMessage,
    db: Session = Depends(get_db)
):
    """
    Endpoint principal del chatbot.
    
    Ejemplo de uso:
    ```json
    {
        "message": "¿Qué productos de limpieza tienen disponibles?",
        "conversation_id": "user123-session456"
    }
    ```
    """
    
    chatbot = ChatbotService(db)
    
    # Obtener o crear conversación
    conv_id = data.conversation_id or f"conv_{datetime.now(UTC).timestamp()}"
    history = conversations.get(conv_id, [])
    
    # Procesar mensaje
    response = await chatbot.process_message(
        user_message=data.message,
        conversation_history=history
    )
    
    # Actualizar historial
    history.append({"role": "user", "content": data.message})
    history.append({"role": "assistant", "content": response["message"]})
    conversations[conv_id] = history[-10:]  # Mantener últimos 10 mensajes
    
    return ChatResponse(
        response=response["message"],
        suggested_products=response.get("products", []),
        actions=response.get("actions", []),
        conversation_id=conv_id
    )

@router.delete("/chat/{conversation_id}")
def clear_conversation(conversation_id: str):
    """Limpia el historial de una conversación"""
    if conversation_id in conversations:
        del conversations[conversation_id]
    return {"message": "Conversación eliminada"}