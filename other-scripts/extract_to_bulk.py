import json

def generate_bulk_for_postman(input_json, output_txt, index_name):
    try:
        # 1. Load your existing JSON file
        with open(input_json, 'r', encoding='utf-8') as f:
            restaurants = json.load(f)
        
        bulk_content = ""
        
        # 2. Extract BusinessID and Cuisine for each record
        for item in restaurants:
            # Create the action metadata line
            action = {"index": {"_index": index_name}}
            
            # Create the data line (only BusinessID and Cuisine)
            # Note: Ensure these keys match your JSON file exactly (Case Sensitive)
            data_record = {
                "BusinessID": item.get("BusinessID"),
                "Cuisine": item.get("Cuisine")
            }
            
            # Append to string with required newlines
            bulk_content += json.dumps(action) + "\n"
            bulk_content += json.dumps(data_record) + "\n"
        
        # 3. Save to the output file
        with open(output_txt, 'w', encoding='utf-8') as f:
            f.write(bulk_content)
            
        print(f"Done! {len(restaurants)} records processed.")
        print(f"Please open '{output_txt}', copy all content, and paste it into Postman.")

    except Exception as e:
        print(f"An error occurred: {e}")

# Run the processing
generate_bulk_for_postman('restaurants_data.json', 'Restaurantindex.txt', 'restaurant_list')