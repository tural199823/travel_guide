import json
import time
from typing import List, Dict, Optional, Union
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from bs4 import BeautifulSoup
import re

# Global cache to avoid re-scraping the same city
_CITY_CACHE = {}
_CACHE_TIMEOUT = 3600  # 1 hour cache

def clear_cache():
    """Clear the event cache to force fresh scraping"""
    global _CITY_CACHE
    _CITY_CACHE.clear()
    print("Cache cleared!")

class EventScraperTool:
    """Event scraper tool optimized for AI agents"""
    
    VALID_CATEGORIES = [
        'disco', 'konzert', 'theater', 'medien', 'sonstige', 
        'kino', 'literatur', 'comedy', 'vortrag', 'kunst'
    ]
    
    @staticmethod
    def get_events_by_category(city: str, category: str, max_events: int = 5, include_descriptions: bool = False, force_refresh: bool = False) -> List[Dict]:
        """
        Get events for a specific city and category
        
        Args:
            city: Name of the city (e.g., 'Berlin', 'Hamburg')
            category: Event category - one of: disco, konzert, theater, medien, 
                     sonstige, kino, literatur, comedy, vortrag, kunst
            max_events: Maximum number of events to return (default: 5)
            include_descriptions: Whether to fetch detailed descriptions (slower, default: False)
            force_refresh: If True, bypass cache and scrape fresh data (default: False)
            
        Returns:
            List of event dictionaries with keys: title, date_time, location, description, event_url
            
        Example:
            events = EventScraperTool.get_events_by_category('Berlin', 'konzert', 3, include_descriptions=True)
            fresh_events = EventScraperTool.get_events_by_category('Berlin', 'konzert', 3, force_refresh=True)
        """
        if category not in EventScraperTool.VALID_CATEGORIES:
            return {
                "error": f"Invalid category '{category}'. Valid categories: {', '.join(EventScraperTool.VALID_CATEGORIES)}"
            }
        
        # Check cache first (unless force refresh is requested)
        cache_key = f"{city.lower()}_{int(time.time() // _CACHE_TIMEOUT)}"
        
        if force_refresh or cache_key not in _CITY_CACHE:
            print(f"Scraping fresh data for {city}...")
            all_events = EventScraperTool._scrape_city_events(city)
            _CITY_CACHE[cache_key] = all_events
        else:
            print(f"Using cached data for {city}")
            all_events = _CITY_CACHE[cache_key]
        
        # Get events for requested category
        category_events = all_events.get(category, [])[:max_events]
        
        # Add descriptions if requested
        if include_descriptions and category_events:
            print(f"Fetching descriptions for {len(category_events)} events...")
            EventScraperTool._add_descriptions_to_events(category_events, category)
        
        return category_events
    
    @staticmethod
    def get_available_categories(city: str) -> Dict[str, int]:
        """
        Get all available categories and their event counts for a city
        
        Args:
            city: Name of the city
            
        Returns:
            Dictionary with category names as keys and event counts as values
        """
        cache_key = f"{city.lower()}_{int(time.time() // _CACHE_TIMEOUT)}"
        
        if cache_key not in _CITY_CACHE:
            all_events = EventScraperTool._scrape_city_events(city)
            _CITY_CACHE[cache_key] = all_events
        else:
            all_events = _CITY_CACHE[cache_key]
        
        return {category: len(events) for category, events in all_events.items() if events}
    
    @staticmethod
    def add_descriptions_to_events(city: str, category: str, max_events: int = 5, force_refresh: bool = False) -> List[Dict]:
        """
        Get events with descriptions for already scraped events
        This is a convenience method that combines get_events_by_category with descriptions
        
        Args:
            city: Name of the city
            category: Event category
            max_events: Maximum number of events to enrich
            force_refresh: If True, bypass cache and scrape fresh data
            
        Returns:
            List of events with descriptions added
        """
        return EventScraperTool.get_events_by_category(city, category, max_events, include_descriptions=True, force_refresh=force_refresh)
    
    @staticmethod
    def _add_descriptions_to_events(events: List[Dict], category: str) -> None:
        """
        Add descriptions to a list of events (modifies in place)
        Skips cinema events as they typically don't have detailed descriptions
        """
        if category == 'kino':
            print("Skipping descriptions for cinema events")
            return
        
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-images')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        
        try:
            for i, event in enumerate(events):
                if not event.get('event_url'):
                    continue
                    
                try:
                    print(f"Fetching description {i+1}/{len(events)}: {event['title'][:50]}...")
                    driver.get(event['event_url'])
                    time.sleep(1)
                    
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    
                    # Try multiple selectors for description
                    description_div = (soup.find('div', class_='beschreibung makelinks') or
                                     soup.find('div', class_='beschreibung') or
                                     soup.find('div', {'class': lambda x: x and 'beschreibung' in str(x).lower()}))
                    
                    if description_div:
                        # Get first 2 paragraphs or first 300 characters
                        paragraphs = description_div.find_all('p')
                        if paragraphs:
                            description = ' '.join(p.text.strip() for p in paragraphs[:2])
                        else:
                            description = description_div.text.strip()
                        
                        # Limit description length
                        if len(description) > 300:
                            description = description[:300] + "..."
                        
                        event['description'] = description
                    else:
                        event['description'] = "No description available"
                        
                except Exception as e:
                    print(f"Error fetching description for {event['title']}: {str(e)}")
                    event['description'] = "Description could not be loaded"
                    continue
                    
        finally:
            driver.quit()
    
    @staticmethod
    def search_events(city: str, keyword: str, max_events: int = 10) -> List[Dict]:
        """
        Search for events containing a keyword across all categories
        
        Args:
            city: Name of the city
            keyword: Search keyword (searches in title, description, location)
            max_events: Maximum number of events to return
            
        Returns:
            List of matching events with category information
        """
        cache_key = f"{city.lower()}_{int(time.time() // _CACHE_TIMEOUT)}"
        
        if cache_key not in _CITY_CACHE:
            all_events = EventScraperTool._scrape_city_events(city)
            _CITY_CACHE[cache_key] = all_events
        else:
            all_events = _CITY_CACHE[cache_key]
        
        matching_events = []
        keyword_lower = keyword.lower()
        
        for category, events in all_events.items():
            for event in events:
                if (keyword_lower in event['title'].lower() or 
                    keyword_lower in event['description'].lower() or
                    keyword_lower in event['location'].lower()):
                    
                    event_with_category = event.copy()
                    event_with_category['category'] = category
                    matching_events.append(event_with_category)
                    
                    if len(matching_events) >= max_events:
                        return matching_events
        
        return matching_events
    
    @staticmethod
    def _scrape_city_events(city_name: str, max_per_category: int = 10) -> Dict[str, List[Dict]]:
        """Internal method to scrape events for a city"""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-images')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        
        events_by_category = {}
        category_counts = {}
        
        try:
            # Direct URL approach (fastest)
            direct_url = f'https://www.wasgehtapp.de/?city={city_name.replace(" ", "+")}'
            driver.get(direct_url)
            time.sleep(2)
            
            # Quick cookie consent
            try:
                WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, '//a[contains(@class, "cmpboxbtn") and contains(text(), "Akzeptieren")]'))
                ).click()
            except:
                pass
            
            # Check for events
            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'termin'))
                )
            except TimeoutException:
                print(f"No events found for {city_name}")
                return events_by_category
            
            # Limited scrolling
            for i in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            event_containers = soup.find_all('div', class_='termin')
            
            if not event_containers:
                return events_by_category
            
            # Process events
            for event in event_containers:
                try:
                    # Get category first
                    category_tag = event.find('div', class_='kat_ind')
                    if category_tag and category_tag.get('class'):
                        category_classes = category_tag.get('class', [])
                        category = category_classes[2] if len(category_classes) > 2 else 'sonstige'
                    else:
                        category = 'sonstige'
                    
                    # Skip if category is full
                    if category_counts.get(category, 0) >= max_per_category:
                        continue
                    
                    # Extract event details
                    title_elem = event.find('h3', class_='titel') or event.find('h3') or event.find('h2')
                    title = title_elem.text.strip().replace('\n', '') if title_elem else 'No title'
                    
                    date_elem = event.find('span', class_='zeit')
                    date = date_elem.text.strip() if date_elem else 'No date'
                    
                    location_elem = event.find('a', class_='location')
                    location = re.sub(r'\s+', ' ', location_elem.text.strip()) if location_elem else 'No location'
                    
                    event_details = {
                        'title': title,
                        'date_time': date,
                        'location': location,
                        'description': '',  # Will be filled later if requested
                        'event_url': ''  # Store URL for description fetching
                    }
                    
                    # Extract event URL for description fetching
                    event_link_tag = event.find('a', class_='target') or event.find('a', href=True)
                    if event_link_tag and 'href' in event_link_tag.attrs:
                        event_link = event_link_tag['href']
                        if event_link.startswith('/'):
                            event_details['event_url'] = f"https://www.wasgehtapp.de{event_link}"
                        elif event_link.startswith('http'):
                            event_details['event_url'] = event_link
                        else:
                            event_details['event_url'] = f"https://www.wasgehtapp.de/{event_link}"
                    
                    # Add to category
                    if category not in events_by_category:
                        events_by_category[category] = []
                        category_counts[category] = 0
                    
                    events_by_category[category].append(event_details)
                    category_counts[category] += 1
                    
                except Exception as e:
                    continue
            
        except Exception as e:
            print(f"Error scraping {city_name}: {e}")
            
        finally:
            driver.quit()
        
        return events_by_category


# Convenience functions for agent use
def get_events(city: str, category: str, max_events: int = 5, with_descriptions: bool = False, force_refresh: bool = False) -> Union[List[Dict], Dict]:
    """
    Simple function to get events for agent use
    
    Usage:
        # Fast - no descriptions
        concerts = get_events('Berlin', 'konzert', 3)
        
        # Slower - with descriptions  
        concerts = get_events('Berlin', 'konzert', 3, with_descriptions=True)
        
        # Fresh data - bypass cache
        fresh_concerts = get_events('Berlin', 'konzert', 3, force_refresh=True)
    """
    return EventScraperTool.get_events_by_category(city, category, max_events, with_descriptions, force_refresh)

def get_events_with_descriptions(city: str, category: str, max_events: int = 5, force_refresh: bool = False) -> Union[List[Dict], Dict]:
    """
    Convenience function to get events WITH descriptions
    
    Usage:
        detailed_concerts = get_events_with_descriptions('Berlin', 'konzert', 3)
        fresh_detailed_concerts = get_events_with_descriptions('Berlin', 'konzert', 3, force_refresh=True)
    """
    return EventScraperTool.add_descriptions_to_events(city, category, max_events, force_refresh)

def get_fresh_events(city: str, category: str, max_events: int = 5, with_descriptions: bool = False) -> Union[List[Dict], Dict]:
    """
    Convenience function to get fresh events (bypasses cache)
    
    Usage:
        fresh_concerts = get_fresh_events('Berlin', 'konzert', 3)
        fresh_detailed_concerts = get_fresh_events('Berlin', 'konzert', 3, with_descriptions=True)
    """
    return EventScraperTool.get_events_by_category(city, category, max_events, with_descriptions, force_refresh=True)

def search_events(city: str, keyword: str, max_events: int = 10) -> List[Dict]:
    """
    Simple function to search events
    
    Usage:
        rock_events = search_events('Berlin', 'rock', 5)
        jazz_events = search_events('Munich', 'jazz')
    """
    return EventScraperTool.search_events(city, keyword, max_events)

def get_categories(city: str) -> Dict[str, int]:
    """
    Get available categories for a city
    
    Usage:
        categories = get_categories('Berlin')
        # Returns: {'konzert': 15, 'theater': 8, 'kino': 12, ...}
    """
    return EventScraperTool.get_available_categories(city)



def get_detailed_events(city: str, category: str, max_events: int) -> str:
    """Get events with descriptions and return as JSON string"""
    detailed_events = get_events_with_descriptions(city=city, category=category, max_events=max_events, force_refresh=True)
    
    if isinstance(detailed_events, dict) and 'error' in detailed_events:
        return json.dumps({"error": detailed_events['error']}, indent=2, ensure_ascii=False)
    
    # Format events as JSON
    events_json = {
        "city": city,
        "category": category,
        "total_events": len(detailed_events),
        "events": []
    }
    
    for i, event in enumerate(detailed_events, 1):
        event_data = {
            "id": i,
            "title": event['title'],
            "date_time": event['date_time'],
            "location": event['location'],
            "description": event['description'],
            "event_url": event.get('event_url', '')
        }
        events_json["events"].append(event_data)
    
    return json.dumps(events_json, indent=2, ensure_ascii=False)