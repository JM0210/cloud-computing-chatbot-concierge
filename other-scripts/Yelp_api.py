import requests
import json
import time

# ================= CONFIGURATION =================
API_KEY = 'i58kFwMch15LR7GL3ERklvYf5gbxK6yIpCgVMEmHwdhhPP4hwvmtHFZl1qFHrawmm2UUhMHlfZlmX7JATTZ9S2pf6FrDY3v7PGFiGkDOhXikO13lzxHhGkBSrxKWa'
# API_key is invalid now
ENDPOINT = 'https://api.yelp.com/v3/businesses/search'
HEADERS = {'Authorization': f'Bearer {API_KEY}'}

# Using 6 cuisines to ensure 6 * 200 = 1200 records (satisfies 1000+ requirement)
CUISINES = ['chinese', 'japanese', 'italian', 'mexican', 'american', 'thai']
LOCATION = 'Manhattan'

# FIXED STRATEGY: 
# limit (40) * 5 iterations = 200 restaurants per cuisine.
# Max offset + limit will be 160 + 40 = 200, which is < 240.
LIMIT_PER_REQUEST = 40
ITERATIONS = 5 
# =================================================

def fetch_restaurants():
    all_restaurants = []
    unique_ids = set()

    for cuisine in CUISINES:
        print(f"--- Processing Cuisine: {cuisine} ---")
        cuisine_count = 0
        
        for i in range(ITERATIONS):
            offset = i * LIMIT_PER_REQUEST
            params = {
                'term': f'{cuisine} restaurants',
                'location': LOCATION,
                'limit': LIMIT_PER_REQUEST,
                'offset': offset
            }
            
            response = requests.get(ENDPOINT, headers=HEADERS, params=params)
            
            if response.status_code == 200:
                businesses = response.json().get('businesses', [])
                if not businesses: break
                
                for biz in businesses:
                    bid = biz['id']
                    if bid not in unique_ids:
                        unique_ids.add(bid)
                        
                        # Requirements from PDF Page 2 [cite: 71]
                        address = " ".join(biz.get('location', {}).get('display_address', []))
                        item = {
                            'BusinessID': bid,
                            'Name': biz.get('name'),
                            'Address': address,
                            'Coordinates': biz.get('coordinates'),
                            'NumberOfReviews': biz.get('review_count'),
                            'Rating': biz.get('rating'),
                            'ZipCode': biz.get('location', {}).get('zip_code'),
                            'Cuisine': cuisine,
                            'insertedAtTimestamp': str(time.time()) # Required field [cite: 70]
                        }
                        all_restaurants.append(item)
                        cuisine_count += 1
                print(f"Iteration {i+1}: Total {cuisine_count} unique items for {cuisine}")
            else:
                print(f"Error {response.status_code}: {response.text}")
                break
            
            time.sleep(0.2) # Avoid throttling

    # Final Save
    with open('restaurants_data.json', 'w', encoding='utf-8') as f:
        json.dump(all_restaurants, f, ensure_ascii=False, indent=4)
    
    print(f"\nFinal Count: {len(all_restaurants)} unique records saved.")

if __name__ == "__main__":
    fetch_restaurants()