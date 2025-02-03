from flask import Flask, request, jsonify
from pydantic import BaseModel, ValidationError, field_validator
import uuid
import re
from typing import List
from datetime import datetime

app = Flask(__name__)

receipts_db = {}

class Item (BaseModel):
    """
        Create a Item Model for easy parsing and data validation
    """
    shortDescription: str
    price: str
    
    @field_validator("price")
    def validate_price(cls, v):
        if not re.match(r"^\d+\.\d{2}$", v):
            raise ValueError("Item price must be in the format '0.00'")
        return v
    
class Receipt(BaseModel):
    """
        Create a Receipt Model for parsing Receipt components as defined in api.yml
    """
    retailer: str
    purchaseDate: str
    purchaseTime: str
    items: List[Item]
    total: str
       
    @field_validator("retailer")
    def validate_retailer(cls, v):
        if not re.match(r"^[\w\s\-&]+$", v):
            raise ValueError("Retailer name price must not be blank")
        return v

    @field_validator("purchaseDate")
    def validate_purchaseDate(cls, v):
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Purchase date must be in the format 'YYYY-MM-DD'")
        
        try:
            purchase_date = datetime.strptime(v , '%Y-%m-%d').date()
            if purchase_date > datetime.today().date():
                raise ValueError("Purchase date cannot be in the future")

        except Exception as err:
            raise ValueError("Purchase date must be correct")
    
        return v
        
    @field_validator("purchaseTime")
    def validate_purchaseTime(cls, v):
        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError("Purchase time must be in the 24h format'HH:MM'")
 
        try:
            #try to convert the time into time object, if invalid time eg. 12:61, it should return error
            datetime.strptime(v, '%H:%M').time()
            

        except Exception as err:
            raise ValueError("Purchase time must be correct")
    
        return v
    
    @field_validator('total')
    def validate_total(cls, v):
        if not re.match(r"^\d+\.\d{2}$", v):
            raise ValueError("Total must be in the format '0.00'")
        return v

def calculate_points(receipt: Receipt):
    """
        Calculate points according to the rules
        Args:
            receipt (Receipt): Pydantic model for receipt
            
        Returns:
            points (int): Returns points earned in the receipt
    """
    points = 0

    # 1. One point for every alphanumeric character in the retailer name.
    points += sum(char.isalnum() for char in receipt.retailer)

    # 2. 50 points if the total is a round dollar amount with no cents.
    if receipt.total.endswith('.00'):
        points += 50

    # 3. 25 points if the total is a multiple of 0.25.
    if float(receipt.total) % 0.25 == 0:
        points += 25

    # 4. 5 points for every two items on the receipt.
    points += (len(receipt.items) // 2) * 5

    # 5. points based on item descriptions.
    for item in receipt.items:
        description = item.shortDescription.strip()
        if len(description) % 3 == 0:
            points += round(float(item.price) * 0.2)

    # 6. 6 points if the day in the purchase date is odd.
    day = datetime.strptime(receipt.purchaseDate, "%Y-%m-%d").day
    if day % 2 != 0:
        points += 6

    # 7. 10 points if the time of purchase is after 2:00pm and before 4:00pm.
    time_obj = datetime.strptime(receipt.purchaseTime, '%H:%M')
    if time_obj.hour in [14, 15]:
        points += 10

    return points

@app.route('/receipts/process', methods=['POST'])
def process_receipt():
    """
        Process and adds a receipt
        Args:
            request: User request
            
        Returns:
            Id: id of the receipt in JSON
        
    """
    try:
        #parse the request in json
        data = request.get_json()
        # f"print(Incoming Data: {data}")  # Debug incoming data
        
        #validate and initialize the request through Pydantic
        receipt = Receipt(**data)
        
        #create uuid as id
        receipt_id = str(uuid.uuid4())
        
        #calculate points here, to avoid multiple creations
        points = calculate_points(receipt)
        
        #store in in-memory
        receipts_db[receipt_id] = points
        

        return jsonify({'id': receipt_id}), 200
    
    
    except ValidationError as e:
        print
        return jsonify({'error': [ {"type": err['type'], "attribute": err['loc'][0], "msg": err['msg'] } for err in e.errors()]}), 400
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    
    except Exception as e:
        return jsonify({'error': "Internal Server Error"}), 500
    

@app.route('/receipts/<receipt_id>/points', methods=['GET'])
def get_points(receipt_id):
    """
        Function to get points earned on a receipt
        Args:
            receipt_id: Id of receipt to check the points
    """
    #check if receipt id is is correct format
    if not re.match(r"^\S+$", receipt_id):
        return jsonify({'error': 'Invalid receipt ID format.'}), 400

    
    points = receipts_db.get(receipt_id)
    #if not exist return not found
    if points is None:
        return jsonify({'error': 'Receipt not found.'}), 404

    #return result
    return jsonify({'points': points}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
