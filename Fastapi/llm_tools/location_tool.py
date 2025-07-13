def process_location_data(location_data):
    # Extract coordinates
    if 'location' in location_data:  
        lat = location_data['location']['latitude']
        lng = location_data['location']['longitude']
    elif 'coords' in location_data: 
        lat = location_data['coords']['latitude']
        lng = location_data['coords']['longitude']
    else:  
        lat = location_data.get('latitude')
        lng = location_data.get('longitude')
    
    # Validate coordinates
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise ValueError("Invalid coordinates")
    
    return lat, lng