import cv2
import numpy as np
import random
import time
from datetime import datetime

class MockCamera:
    def __init__(self, width=640, height=480, num_people=4):
        self.width = width
        self.height = height
        self.num_people = num_people
        
        # Initialize simulated people with organic positions and velocities
        self.people = []
        for i in range(num_people):
            # Assign specific behaviors to different simulated tracks
            behavior = 'normal'
            if i == 0:
                behavior = 'intruder'  # Will walk into the restricted zone
            elif i == 1:
                behavior = 'runner'    # Will move fast back and forth
            elif i == 2:
                behavior = 'loiterer'  # Will stay in one spot
            elif i == 3:
                behavior = 'weapon_carrier' # Carries a suspicious weapon
                
            self.people.append({
                'id': i,
                'x': random.randint(100, width - 100),
                'y': random.randint(150, height - 100),
                'vx': random.uniform(-1.5, 1.5),
                'vy': random.uniform(-1.5, 1.5),
                'w': 40,
                'h': 90,
                'behavior': behavior,
                'birth_time': time.time()
            })
            
        # Static desk coordinates for office instruments
        self.instruments = [
            {'name': 'LAPTOP', 'x': 140, 'y': 280, 'w': 50, 'h': 40, 'cls': 'LAPTOP'},
            {'name': 'BOTTLE', 'x': 210, 'y': 250, 'w': 18, 'h': 45, 'cls': 'BOTTLE'},
            {'name': 'NOTEBOOK', 'x': 260, 'y': 290, 'w': 40, 'h': 35, 'cls': 'NOTEBOOK'},
            {'name': 'PEN', 'x': 290, 'y': 310, 'w': 8, 'h': 24, 'cls': 'PEN'},
            {'name': 'KEYS', 'x': 100, 'y': 295, 'w': 22, 'h': 16, 'cls': 'KEYS'}
        ]
        
        # Default restricted zone polygon points (same as backend defaults)
        self.default_zone = np.array([
            [320, 180],
            [600, 180],
            [600, 420],
            [400, 420]
        ], dtype=np.int32)
        
    def update(self, zone_poly=None):
        """Updates simulated human paths organically according to assigned behaviors."""
        current_time = time.time()
        
        if zone_poly is None:
            zone_poly = self.default_zone
            
        for p in self.people:
            # Behavioral path steering
            if p['behavior'] == 'intruder':
                # Slowly steer towards the center of the restricted zone
                if len(zone_poly) > 0:
                    cx = int(np.mean(zone_poly[:, 0]))
                    cy = int(np.mean(zone_poly[:, 1]))
                    
                    dx = cx - p['x']
                    dy = cy - p['y']
                    dist = np.sqrt(dx**2 + dy**2)
                    
                    if dist > 10:
                        p['vx'] = (dx / dist) * 1.8
                        p['vy'] = (dy / dist) * 1.8
                    else:
                        # Once inside, wander slowly inside the zone
                        p['behavior'] = 'intruder_wandering'
            
            elif p['behavior'] == 'intruder_wandering':
                # Walk slowly inside the restricted area bounds
                p['vx'] += random.uniform(-0.1, 0.1)
                p['vy'] += random.uniform(-0.1, 0.1)
                p['vx'] = np.clip(p['vx'], -0.8, 0.8)
                p['vy'] = np.clip(p['vy'], -0.8, 0.8)
                
            elif p['behavior'] == 'runner':
                # Move rapidly back and forth horizontally
                p['vx'] = 5.2 if p['vx'] >= 0 else -5.2
                p['vy'] += random.uniform(-0.2, 0.2)
                p['vy'] = np.clip(p['vy'], -1.0, 1.0)
                
            elif p['behavior'] == 'loiterer':
                # Stay in one small area, shifting organically
                p['vx'] = random.uniform(-0.2, 0.2)
                p['vy'] = random.uniform(-0.2, 0.2)
                
            else: # Standard walking pattern
                p['vx'] += random.uniform(-0.2, 0.2)
                p['vy'] += random.uniform(-0.2, 0.2)
                max_speed = 2.0
                p['vx'] = np.clip(p['vx'], -max_speed, max_speed)
                p['vy'] = np.clip(p['vy'], -max_speed, max_speed)
                
            # Apply velocities
            p['x'] += p['vx']
            p['y'] += p['vy']
            
            # Boundary collision checking (keep within screen margins)
            margin_x = p['w'] // 2 + 10
            margin_y = p['h'] // 2 + 10
            
            if p['x'] < margin_x:
                p['x'] = margin_x
                p['vx'] *= -1
            elif p['x'] > self.width - margin_x:
                p['x'] = self.width - margin_x
                p['vx'] *= -1
                
            if p['y'] < margin_y:
                p['y'] = margin_y
                p['vy'] *= -1
            elif p['y'] > self.height - margin_y:
                p['y'] = self.height - margin_y
                p['vy'] *= -1

    def get_frame_and_detections(self, custom_polygon=None):
        """
        Generates a synthetic camera image and returns simulated detections list.
        Detections are formatted in the exact same format as YoloDetector.
        """
        zone_poly = custom_polygon if custom_polygon is not None else self.default_zone
        self.update(zone_poly)
        
        # 1. Draw CCTV background feed
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:, :] = [26, 17, 15]  # Deep dark tech blueprint blue-grey
        
        # Draw high-tech aesthetic grid
        grid_spacing = 40
        for x in range(0, self.width, grid_spacing):
            cv2.line(frame, (x, 0), (x, self.height), (35, 25, 22), 1)
        for y in range(0, self.height, grid_spacing):
            cv2.line(frame, (0, y), (self.width, y), (35, 25, 22), 1)
            
        # Draw wood desk surface in bottom-left corner
        desk_poly = np.array([[40, 230], [330, 230], [350, 360], [40, 360]], dtype=np.int32)
        overlay_desk = frame.copy()
        cv2.fillPoly(overlay_desk, [desk_poly], (50, 40, 35))
        cv2.polylines(overlay_desk, [desk_poly], True, (75, 65, 60), 1)
        cv2.addWeighted(overlay_desk, 0.4, frame, 0.6, 0, frame)
        
        # Draw tech labels
        cv2.putText(frame, "SYNTHETIC FEED // LAB_OFFICE_03", (20, 38), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 100), 1, cv2.LINE_AA)
        
        detections = []
        
        # 2. Draw Simulated Office Instruments on the desk
        for inst in self.instruments:
            x, y, w, h = inst['x'], inst['y'], inst['w'], inst['h']
            x1, y1 = x - w // 2, y - h // 2
            x2, y2 = x + w // 2, y + h // 2
            
            # Render individual custom shapes
            if inst['name'] == 'LAPTOP':
                cv2.rectangle(frame, (x1, y1 + 10), (x2, y2), (180, 180, 180), -1)
                cv2.rectangle(frame, (x1 + 4, y1), (x2 - 4, y1 + 12), (120, 120, 120), -1)
                cv2.rectangle(frame, (x1 + 6, y1 + 2), (x2 - 6, y1 + 10), (220, 220, 200), -1)
            elif inst['name'] == 'BOTTLE':
                cv2.rectangle(frame, (x1, y1 + 8), (x2, y2), (200, 100, 50), -1)
                cv2.rectangle(frame, (x1 + 4, y1), (x2 - 4, y1 + 8), (80, 80, 80), -1)
            elif inst['name'] == 'NOTEBOOK':
                cv2.rectangle(frame, (x1, y1), (x2, y2), (240, 240, 240), -1)
                cv2.rectangle(frame, (x1 + 2, y1 + 2), (x2 - 2, y2 - 2), (220, 220, 220), -1)
                cv2.line(frame, (x, y1), (x, y2), (50, 50, 180), 2)
            elif inst['name'] == 'PEN':
                cv2.line(frame, (x1, y1), (x2, y2), (40, 40, 40), 2)
                cv2.circle(frame, (x2, y2), 2, (10, 10, 180), -1)
            elif inst['name'] == 'KEYS':
                cv2.circle(frame, (x, y), 5, (100, 180, 180), 1)
                cv2.line(frame, (x + 3, y + 3), (x2, y2), (180, 180, 180), 2)
            
            conf = random.uniform(0.85, 0.96)
            detections.append({
                'track_id': None,
                'class': inst['cls'],
                'bbox': [x1, y1, x2, y2],
                'conf': conf,
                'feet': (x, y2)
            })
            
        # 3. Draw Simulated Human Capsules
        for p in self.people:
            x, y, w, h = int(p['x']), int(p['y']), p['w'], p['h']
            x1, y1 = x - w // 2, y - h // 2
            x2, y2 = x + w // 2, y + h // 2
            
            # Capsule visualization: Head circle + shoulders ellipse + legs
            head_r = 11
            cv2.circle(frame, (x, y1 + head_r), head_r, (120, 120, 120), -1)
            cv2.ellipse(frame, (x, y1 + 38), (w // 2, 24), 0, 0, 360, (95, 95, 95), -1)
            cv2.line(frame, (x - 8, y1 + 58), (x - 8, y2 - 5), (70, 70, 70), 3)
            cv2.line(frame, (x + 8, y1 + 58), (x + 8, y2 - 5), (70, 70, 70), 3)
            
            # A. If runner, draw quick velocity speed dashes behind
            if p['behavior'] == 'runner':
                dash_color = (180, 180, 180)
                offset = 15 if p['vx'] < 0 else -15
                cv2.line(frame, (x + offset, y - 10), (x + offset + (20 if p['vx'] < 0 else -20), y - 10), dash_color, 1)
                cv2.line(frame, (x + offset - 5, y + 10), (x + offset - 5 + (20 if p['vx'] < 0 else -20), y + 10), dash_color, 1)
                
            # B. If carrying a weapon, draw a distinct metallic grey object in their hand
            if p['behavior'] == 'weapon_carrier':
                # Draw a metallic grey rectangle representing a rifle/handgun held diagonally
                cv2.line(frame, (x - 12, y + 25), (x + 15, y + 5), (140, 145, 150), 4) # Barrel
                cv2.rectangle(frame, (x - 4, y + 15), (x + 4, y + 25), (60, 60, 60), -1) # Grip
                
                # Append a weapon detection bounding box centered near the person's hand
                w_x1, w_y1 = x - 18, y
                w_x2, w_y2 = x + 18, y + 30
                
                detections.append({
                    'track_id': None,
                    'class': 'WEAPON',
                    'bbox': [w_x1, w_y1, w_x2, w_y2],
                    'conf': random.uniform(0.88, 0.94),
                    'feet': (x, w_y2)
                })
                
            conf = random.uniform(0.88, 0.97)
            detections.append({
                'track_id': p['id'],
                'class': 'PERSON',
                'bbox': [x1, y1, x2, y2],
                'conf': conf,
                'feet': (x, y2)
            })
            
        return frame, detections