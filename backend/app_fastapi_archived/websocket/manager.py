from typing import List, Dict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # Maps event categories to lists of connected WebSocket instances
        self.active_connections: Dict[str, List[WebSocket]] = {
            "telemetry": [],  # Real-time bbox updates, overlays coordinates, and system stats
            "alerts": []      # Serious alert broadcasts containing details, descriptions, snapshots
        }

    async def connect(self, websocket: WebSocket, channel: str):
        """Accepts and indexes a new client socket connection under a specified channel."""
        await websocket.accept()
        if channel in self.active_connections:
            self.active_connections[channel].append(websocket)
            print(f"WS Manager: New connection established on channel [{channel}] (Total: {len(self.active_connections[channel])})")
        else:
            await websocket.close(code=1003)  # Unsupported data format

    def disconnect(self, websocket: WebSocket, channel: str):
        """Removes a client socket from active pools on disconnect."""
        if channel in self.active_connections and websocket in self.active_connections[channel]:
            self.active_connections[channel].remove(websocket)
            print(f"WS Manager: Connection terminated on channel [{channel}] (Total: {len(self.active_connections[channel])})")

    async def connect_telemetry(self, websocket: WebSocket):
        await self.connect(websocket, "telemetry")

    def disconnect_telemetry(self, websocket: WebSocket):
        self.disconnect(websocket, "telemetry")

    async def connect_alerts(self, websocket: WebSocket):
        await self.connect(websocket, "alerts")

    def disconnect_alerts(self, websocket: WebSocket):
        self.disconnect(websocket, "alerts")

    async def broadcast_json(self, message: dict, channel: str):
        """Asynchronously dispatches a JSON dict package to all live sockets inside a channel."""
        if channel not in self.active_connections:
            return
            
        dead_connections = []
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception:
                # Connection might have died abruptly without triggering standard close handlers
                dead_connections.append(connection)
                
        # Clean up stale dead connections
        for dead in dead_connections:
            if dead in self.active_connections[channel]:
                self.active_connections[channel].remove(dead)

    def broadcast_telemetry(self, telemetry: dict):
        """Thread-safe synchronous wrapper to dispatch telemetry JSON to the async loop."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast_json(telemetry, "telemetry"), loop)
            else:
                loop.run_until_complete(self.broadcast_json(telemetry, "telemetry"))
        except RuntimeError:
            asyncio.run(self.broadcast_json(telemetry, "telemetry"))

    def broadcast_alert(self, alert: dict):
        """Thread-safe synchronous wrapper to dispatch alert JSON to the async loop."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast_json(alert, "alerts"), loop)
            else:
                loop.run_until_complete(self.broadcast_json(alert, "alerts"))
        except RuntimeError:
            asyncio.run(self.broadcast_json(alert, "alerts"))

manager = ConnectionManager()

