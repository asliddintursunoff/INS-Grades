import os
import json
import asyncio
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

django_http_app = get_asgi_application()


async def handle_payment_websocket(scope, receive, send):
    """
    Handles native ASGI WebSocket connections for live payment status updates.
    Route: /ws/payments/<transaction_id>/
    """
    from asgiref.sync import sync_to_async
    from api.models import PaymentTransaction
    from django.utils import timezone

    path = scope.get('path', '')
    parts = [p for p in path.strip('/').split('/') if p]

    # Expecting /ws/payments/<transaction_id>/
    if len(parts) < 3 or parts[0] != 'ws' or parts[1] != 'payments':
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.send", "text": json.dumps({"error": "Invalid WebSocket path"})})
        await send({"type": "websocket.close", "code": 4000})
        return

    tx_id = parts[2]

    # Accept connection
    await send({"type": "websocket.accept"})

    @sync_to_async
    def check_transaction():
        try:
            tx = PaymentTransaction.objects.select_related('student').get(transaction_id=tx_id)
            now = timezone.now()
            if tx.status == 'pending' and now > tx.expires_at:
                tx.status = 'expired'
                tx.save(update_fields=['status'])
            seconds_left = max(0, int((tx.expires_at - now).total_seconds())) if tx.status == 'pending' else 0
            return {
                "transaction_id": str(tx.transaction_id),
                "status": tx.status,
                "total_amount": tx.total_amount,
                "seconds_remaining": seconds_left,
                "is_premium": tx.student.has_premium,
                "completed_at": tx.completed_at.isoformat() if tx.completed_at else None
            }
        except (PaymentTransaction.DoesNotExist, ValueError):
            return None

    # Continuous monitor loop (every 1.5s)
    try:
        while True:
            # Check if client sent disconnect or message
            try:
                msg = await asyncio.wait_for(receive(), timeout=0.05)
                if msg.get('type') == 'websocket.disconnect':
                    break
            except asyncio.TimeoutError:
                pass

            data = await check_transaction()
            if not data:
                await send({"type": "websocket.send", "text": json.dumps({"error": "Transaction not found"})})
                await send({"type": "websocket.close", "code": 4004})
                break

            await send({"type": "websocket.send", "text": json.dumps(data)})

            if data['status'] == 'completed':
                await asyncio.sleep(0.5)
                await send({"type": "websocket.close", "code": 1000})
                break
            elif data['status'] in ('expired', 'cancelled'):
                await asyncio.sleep(0.5)
                await send({"type": "websocket.close", "code": 1000})
                break

            await asyncio.sleep(1.5)
    except Exception:
        pass


async def application(scope, receive, send):
    """
    Main ASGI router: delegates http to Django HTTP application,
    and websocket to native payment handler.
    """
    if scope['type'] == 'http':
        await django_http_app(scope, receive, send)
    elif scope['type'] == 'websocket':
        await handle_payment_websocket(scope, receive, send)
    elif scope['type'] == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                await send({'type': 'lifespan.shutdown.complete'})
                return
