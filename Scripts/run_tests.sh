#!/bin/bash
# scripts/run_tests.sh
# Script para ejecutar todos los tests con cobertura

echo "=========================================="
echo "🧪 Ejecutando Tests del Sistema POS"
echo "=========================================="

# Colores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "\n${BLUE}📦 Instalando dependencias de testing...${NC}"
pip install pytest pytest-cov httpx

echo -e "\n${BLUE}🧹 Limpiando archivos de cache...${NC}"
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete

echo -e "\n${BLUE}🧪 Ejecutando tests con cobertura...${NC}"
pytest tests/ -v \
    --cov=app \
    --cov=crud \
    --cov=models \
    --cov-report=term-missing \
    --cov-report=html \
    --tb=short

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✅ Todos los tests pasaron exitosamente!${NC}"
    echo -e "\n📊 Reporte de cobertura generado en: htmlcov/index.html"
else
    echo -e "\n❌ Algunos tests fallaron"
    exit 1
fi