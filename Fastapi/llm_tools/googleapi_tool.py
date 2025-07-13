import requests
import pandas as pd
import json
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from typing import Annotated, Dict, Any, Optional
import time
try:
    from nltk.corpus import stopwords
    from sklearn.feature_extraction.text import CountVectorizer
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.summarizers.lsa import LsaSummarizer
    SUMMARIZATION_AVAILABLE = True
except ImportError:
    SUMMARIZATION_AVAILABLE = False
    print("Warning: Summarization libraries not available. Install with:")
    print("pip install nltk scikit-learn sumy")
    print("python -c \"import nltk; nltk.download('stopwords'); nltk.download('punkt')\"")



class TravelAssistant:
    """Enhanced travel assistant with better error handling and performance."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()  # Reuse connections
        
    def _make_request(self, url: str, params: Dict, max_retries: int = 3) -> Dict:
        """Make HTTP request with retry logic."""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise Exception(f"API request failed after {max_retries} attempts: {str(e)}")
                time.sleep(0.5 * (attempt + 1))  # Exponential backoff
    
    def _fetch_place_details(self, place_id: str, name: str) -> Tuple[str, Dict]:
        """Fetch details for a single place."""
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "key": self.api_key,
            "fields": "reviews,editorial_summary,geometry,dine_in"  # Only request needed fields
        }
        
        try:
            data = self._make_request(url, params)
            return name, data.get('result', {})
        except Exception as e:
            print(f"Warning: Failed to fetch details for {name}: {str(e)}")
            return name, {}
    
    def _get_unique_names(self, names: List[str]) -> List[str]:
        """Generate unique names for places with duplicates."""
        name_counts = {}
        unique_names = []
        
        for name in names:
            if name not in name_counts:
                name_counts[name] = 1
                unique_names.append(name)
            else:
                name_counts[name] += 1
                unique_names.append(f"{name} ({name_counts[name]})")
        
        return unique_names
    
    def _summarize_reviews(self, reviews_dict: Dict[str, List[str]], num_sentences: int = 3) -> Dict[str, str]:
        """Summarize reviews for each place."""
        if not SUMMARIZATION_AVAILABLE:
            # Simple fallback: just join first few reviews
            return {
                name: " ".join(reviews[:2]) if reviews else "No reviews available"
                for name, reviews in reviews_dict.items()
            }
        
        try:
            # Setup German stop words (since API uses German)
            german_stop_words = set(stopwords.words('german'))
            words_to_keep = {'nicht', 'nein', 'kein'}
            custom_stop_words = german_stop_words - words_to_keep
            
            summaries = {}
            for place_name, reviews in reviews_dict.items():
                if not reviews:
                    summaries[place_name] = "No reviews available"
                    continue
                
                # Concatenate all reviews
                all_reviews = " ".join(filter(None, reviews))
                if not all_reviews.strip():
                    summaries[place_name] = "No reviews available"
                    continue
                
                # Remove stop words
                tokens = all_reviews.split()
                filtered_text = " ".join([w for w in tokens if w.lower() not in custom_stop_words])
                
                # Summarize using LSA
                try:
                    parser = PlaintextParser.from_string(filtered_text, Tokenizer("german"))
                    summarizer = LsaSummarizer()
                    summary = summarizer(parser.document, sentences_count=num_sentences)
                    summary_text = " ".join(str(sentence) for sentence in summary)
                    summaries[place_name] = summary_text if summary_text.strip() else "Unable to summarize reviews"
                except Exception:
                    # Fallback to first review if summarization fails
                    summaries[place_name] = reviews[0] if reviews[0] else "No reviews available"
            
            return summaries
        except Exception as e:
            print(f"Warning: Review summarization failed: {str(e)}")
            return {name: " ".join(reviews[:1]) for name, reviews in reviews_dict.items()}
    
    def find_nearby_places(self, lat: float, lng: float, topics: str, 
                          radius: int = 2000, max_places: int = 20,
                          open_now: bool = True) -> Dict:
        """
        Find nearby places based on location and topics.
        
        Args:
            lat: Latitude
            lng: Longitude  
            topics: Search keywords (e.g., "restaurant, asian, cheap")
            radius: Search radius in meters (default: 2000)
            max_places: Maximum number of places to return
            open_now: Only return places open now
            
        Returns:
            Dictionary with place information and saves to scraped_data.json
        """
        
        # Step 1: Search for nearby places
        search_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        search_params = {
            "keyword": topics,
            "location": f"{lat},{lng}",
            "radius": radius,
            "key": self.api_key,
            "opennow": open_now
        }
        
        try:
            search_data = self._make_request(search_url, search_params)
            places = search_data.get('results', [])[:max_places]
            
            if not places:
                return {"error": "No places found matching your criteria"}
            
        except Exception as e:
            raise Exception(f"Failed to search for nearby places: {str(e)}")
        
        # Step 2: Extract basic information
        basic_info = []
        place_ids = []
        
        for place in places:
            basic_info.append({
                'name': place.get('name', 'Unknown'),
                'rating': place.get('rating'),
                'price_level': place.get('price_level'),
                'place_id': place.get('place_id')
            })
            place_ids.append(place.get('place_id'))
        
        # Generate unique names
        names = [info['name'] for info in basic_info]
        unique_names = self._get_unique_names(names)
        
        # Step 3: Fetch detailed information in parallel
        place_details = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_place = {
                executor.submit(self._fetch_place_details, place_id, name): (place_id, name)
                for place_id, name in zip(place_ids, unique_names) if place_id
            }
            
            for future in as_completed(future_to_place):
                try:
                    name, details = future.result()
                    place_details[name] = details
                except Exception as e:
                    place_id, name = future_to_place[future]
                    print(f"Warning: Failed to get details for {name}: {str(e)}")
                    place_details[name] = {}
        
        # Step 4: Calculate distances
        valid_coords = {}
        for i, name in enumerate(unique_names):
            details = place_details.get(name, {})
            geometry = details.get('geometry', {})
            location = geometry.get('location', {})
            if location.get('lat') and location.get('lng'):
                valid_coords[name] = location
        
        distances = {}
        if valid_coords:
            try:
                destination_coords = "|".join([f"{v['lat']},{v['lng']}" for v in valid_coords.values()])
                distance_url = "https://maps.googleapis.com/maps/api/distancematrix/json"
                distance_params = {
                    "destinations": destination_coords,
                    "origins": f"{lat},{lng}",
                    "mode": "walking",
                    "key": self.api_key,
                }
                
                distance_data = self._make_request(distance_url, distance_params)
                
                # Better error handling for distance matrix response
                if distance_data.get('status') != 'OK':
                    raise Exception(f"Distance Matrix API error: {distance_data.get('status', 'Unknown error')}")
                
                rows = distance_data.get('rows', [])
                if not rows:
                    raise Exception("No distance data returned")
                
                elements = rows[0].get('elements', [])
                if len(elements) != len(valid_coords):
                    print(f"Warning: Expected {len(valid_coords)} distances, got {len(elements)}")
                
                # Match distances to places more safely
                coord_names = list(valid_coords.keys())
                for i, name in enumerate(coord_names):
                    if i < len(elements):
                        element = elements[i]
                        if element.get('status') == 'OK' and 'distance' in element:
                            distances[name] = element['distance']['text']
                        else:
                            distances[name] = f"Distance unavailable ({element.get('status', 'unknown error')})"
                    else:
                        distances[name] = "Distance unavailable (no data)"
                        
            except Exception as e:
                print(f"Warning: Distance calculation failed: {str(e)}")
                distances = {name: "Distance unavailable" for name in valid_coords.keys()}
                
        # Step 5: Process reviews and create final dataset
        reviews_by_place = {}
        final_results = []
        
        for i, name in enumerate(unique_names):
            details = place_details.get(name, {})
            
            # Extract reviews
            reviews = [review.get('text', '') for review in details.get('reviews', [])]
            reviews_by_place[name] = [r for r in reviews if r]  # Filter empty reviews
            
            # Compile place information
            place_info = {
                'Name': name,
                'Rating': basic_info[i]['rating'],
                'Price_Level': basic_info[i]['price_level'],
                'Place_ID': basic_info[i]['place_id'],
                'Google_Maps_Link': f"https://www.google.com/maps?q=place_id:{basic_info[i]['place_id']}" if basic_info[i]['place_id'] else None,
                'Distance': distances.get(name, "Distance unavailable"),
                'Dine_In_Available': details.get('dine_in'),
                'Description': details.get('editorial_summary', {}).get('overview'),
                'Coordinates': details.get('geometry', {}).get('location'),
                'Review_Count': len(reviews_by_place[name])
            }
            final_results.append(place_info)
        
        # Step 6: Summarize reviews
        print("Summarizing reviews...")
        review_summaries = self._summarize_reviews(reviews_by_place)
        
        # Add summaries to results
        for result in final_results:
            result['Review_Summary'] = review_summaries.get(result['Name'], "No reviews available")
        
        # Step 7: Save results
        output_data = {
            'search_parameters': {
                'latitude': lat,
                'longitude': lng,
                'topics': topics,
                'radius': radius,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            },
            'places': final_results
        }
        
        return output_data
