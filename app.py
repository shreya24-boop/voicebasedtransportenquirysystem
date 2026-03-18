from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import hashlib
import uuid
import os
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'transport_user',
    'password': 'Yashas@12890',
    'database': 'teq'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route('/api/voice-login', methods=['POST'])
def voice_login():
    data = request.get_json()
    username = data.get('username', '').lower()
    
    # In a real system, we would verify the voiceprint here
    # For demo purposes, we'll just check if the username exists
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if user:
            # Simulate voiceprint verification success
            return jsonify({
                'success': True,
                'message': 'Voice login successful',
                'user': {
                    'user_id': user['user_id'],
                    'username': user['username'],
                    'full_name': user['full_name'],
                    'email': user['email']
                }
            })
        else:
            # User doesn't exist, create a demo user
            cursor.execute(
                "INSERT INTO users (username, voiceprint_hash, full_name, email) VALUES (%s, %s, %s, %s)",
                (username, hashlib.sha256(username.encode()).hexdigest(), 
                 username.capitalize(), f"{username}@example.com")
            )
            conn.commit()
            user_id = cursor.lastrowid
            
            return jsonify({
                'success': True,
                'message': 'New user created and logged in',
                'user': {
                    'user_id': user_id,
                    'username': username,
                    'full_name': username.capitalize(),
                    'email': f"{username}@example.com"
                }
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/search-transport', methods=['POST'])
def search_transport():
    data = request.get_json()
    origin = data.get('origin', '').title()
    destination = data.get('destination', '').title()
    user_id = data.get('user_id')
    
    # Log the search command
    log_voice_command(user_id, f"search from {origin} to {destination}")
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Search for routes
        cursor.execute("""
            SELECT r.route_id, r.origin, r.destination, m.mode_name, 
                   s.departure_time, s.arrival_time, 
                   ROUND(r.distance_km * 2.5, 2) as price
            FROM routes r
            JOIN transport_modes m ON r.mode_id = m.mode_id
            JOIN schedules s ON s.route_id = r.route_id
            WHERE r.origin LIKE %s AND r.destination LIKE %s
            ORDER BY s.departure_time
            LIMIT 5
        """, (f"%{origin}%", f"%{destination}%"))
        
        routes = cursor.fetchall()
        
        if routes:
            # Format times for display
            for route in routes:
                route['departure_time'] = format_time(route['departure_time'])
                route['arrival_time'] = format_time(route['arrival_time'])
            
            return jsonify({
                'success': True,
                'routes': routes,
                'message': f"Found {len(routes)} transport options"
            })
        else:
            # If no routes found, return some demo data
            demo_routes = [
                {
                    'route_id': 1,
                    'origin': origin,
                    'destination': destination,
                    'mode_name': 'Bus',
                    'departure_time': '08:00 AM',
                    'arrival_time': '02:00 PM',
                    'price': 500.00
                },
                {
                    'route_id': 2,
                    'origin': origin,
                    'destination': destination,
                    'mode_name': 'Train',
                    'departure_time': '10:30 AM',
                    'arrival_time': '04:15 PM',
                    'price': 350.00
                }
            ]
            return jsonify({
                'success': True,
                'routes': demo_routes,
                'message': f"Found {len(demo_routes)} transport options"
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/book-ticket', methods=['POST'])
def book_ticket():
    data = request.get_json()
    route_id = data.get('route_id')
    user_id = data.get('user_id')
    travel_date = data.get('travel_date')
    
    # Log the booking command
    log_voice_command(user_id, f"book ticket for route {route_id}")
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get route price (in real app this would be more complex)
        cursor.execute("""
            SELECT ROUND(distance_km * 2.5, 2) as price 
            FROM routes WHERE route_id = %s
        """, (route_id,))
        route = cursor.fetchone()
        price = route['price'] if route else 500.00
        
        # Create booking
        cursor.execute("""
            INSERT INTO bookings (user_id, schedule_id, travel_date, seats, status)
            VALUES (%s, (SELECT schedule_id FROM schedules WHERE route_id = %s LIMIT 1), %s, 1, 'pending')
        """, (user_id, route_id, travel_date))
        conn.commit()
        booking_id = cursor.lastrowid
        
        return jsonify({
            'success': True,
            'booking_id': booking_id,
            'amount': price,
            'message': 'Booking created successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/process-payment', methods=['POST'])
def process_payment():
    data = request.get_json()
    user_id = data.get('user_id')
    amount = data.get('amount')
    
    # Log the payment command
    log_voice_command(user_id, f"make payment of {amount}")
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get the latest pending booking for the user
        cursor.execute("""
            SELECT booking_id FROM bookings 
            WHERE user_id = %s AND status = 'pending'
            ORDER BY booking_time DESC LIMIT 1
        """, (user_id,))
        booking = cursor.fetchone()
        
        if not booking:
            return jsonify({'success': False, 'message': 'No pending bookings found'})
        
        booking_id = booking['booking_id']
        transaction_id = str(uuid.uuid4())[:8].upper()
        
        # Create payment record
        cursor.execute("""
            INSERT INTO payments (booking_id, amount, payment_method, status, transaction_id)
            VALUES (%s, %s, 'voice_confirmation', 'completed', %s)
        """, (booking_id, amount, transaction_id))
        
        # Update booking status
        cursor.execute("""
            UPDATE bookings SET status = 'confirmed' WHERE booking_id = %s
        """, (booking_id,))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'transaction_id': transaction_id,
            'message': 'Payment processed successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

def log_voice_command(user_id, command_text):
    """Log voice commands for analytics and debugging"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO voice_command_logs (user_id, command_text)
            VALUES (%s, %s)
        """, (user_id, command_text))
        conn.commit()
    except Exception as e:
        print(f"Failed to log voice command: {e}")
    finally:
        cursor.close()
        conn.close()

def format_time(time_str):
    """Format database time to AM/PM format"""
    if isinstance(time_str, str):
        return time_str  # Already formatted
    elif isinstance(time_str, timedelta):
        hours = time_str.seconds // 3600
        minutes = (time_str.seconds % 3600) // 60
        period = 'AM' if hours < 12 else 'PM'
        hours = hours % 12
        hours = 12 if hours == 0 else hours
        return f"{hours}:{minutes:02d} {period}"
    return time_str

if __name__ == '__main__':
    app.run(debug=True, port=5000)