FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 appuser

COPY backend/app ./app
COPY backend/rag_sources ./rag_sources
COPY index.html ./rag_sources/index.html
COPY Manual_tecnico_OVA_Modelo_Tres_Lineas_actualizado_2026.pdf ./rag_sources/Manual_tecnico_OVA_Modelo_Tres_Lineas_actualizado_2026.pdf
COPY Manual_usuario_OVA_Modelo_Tres_Lineas_actualizado_2026.pdf ./rag_sources/Manual_usuario_OVA_Modelo_Tres_Lineas_actualizado_2026.pdf
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

