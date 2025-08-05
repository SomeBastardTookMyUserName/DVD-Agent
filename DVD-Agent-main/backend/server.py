from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import asyncio
import httpx
import hashlib
import json
import sqlite3
from contextlib import contextmanager
import requests
from bs4 import BeautifulSoup
import re
import time
import random

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(
    title="DVD Store Data Collection API",
    description="API for collecting DVD store information with email discovery",
    version="1.0.0"
)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hunter.io Configuration
HUNTER_API_KEY = "055a01a67d2f8688f79899bf2794226d5cbdaa02"
HUNTER_BASE_URL = "https://api.hunter.io/v2"

# Models
class DVDStore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    email_confidence: Optional[float] = None
    source: str  # "directory", "reddit", "manual"
    source_url: Optional[str] = None
    notes: Optional[str] = None
    verified: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class DVDStoreCreate(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    source: str = "manual"
    source_url: Optional[str] = None
    notes: Optional[str] = None

class EmailSearchRequest(BaseModel):
    domain: str = Field(..., description="Domain name to search for emails")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None

class SearchJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_type: str  # "directory_search", "reddit_search", "email_discovery"
    status: str = "pending"  # pending, running, completed, failed
    parameters: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    stores_found: int = 0
    credits_used: float = 0.0

# Hunter.io Client
class HunterAPIClient:
    def __init__(self):
        self.api_key = HUNTER_API_KEY
        self.base_url = HUNTER_BASE_URL
        self.request_timestamps = []
        
    async def _enforce_rate_limit(self):
        """Enforce rate limiting to prevent API errors"""
        current_time = datetime.now().timestamp()
        
        # Remove timestamps older than 1 minute
        cutoff_time = current_time - 60
        self.request_timestamps = [ts for ts in self.request_timestamps if ts > cutoff_time]
        
        # Check per-minute limit (500 requests)
        if len(self.request_timestamps) >= 500:
            sleep_time = 60 - (current_time - self.request_timestamps[0])
            if sleep_time > 0:
                logger.warning(f"Rate limit approaching, sleeping for {sleep_time:.2f} seconds")
                await asyncio.sleep(sleep_time)
        
        # Check per-second limit (15 requests)
        recent_requests = [ts for ts in self.request_timestamps if ts > current_time - 1]
        if len(recent_requests) >= 15:
            await asyncio.sleep(1.0)
        
        self.request_timestamps.append(current_time)
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make authenticated request to Hunter.io API"""
        await self._enforce_rate_limit()
        
        params["api_key"] = self.api_key
        url = f"{self.base_url}/{endpoint}"
        
        try:
            async with httpx.AsyncClient(timeout=30) as http_client:
                response = await http_client.get(url, params=params)
                
                if response.status_code == 403:
                    raise HTTPException(status_code=429, detail="Rate limit exceeded or insufficient credits")
                elif response.status_code == 401:
                    raise HTTPException(status_code=401, detail="Invalid API key")
                elif response.status_code != 200:
                    raise HTTPException(status_code=response.status_code, detail=f"API request failed: {response.text}")
                
                return response.json()
                
        except httpx.TimeoutException:
            raise HTTPException(status_code=408, detail="Request timeout")
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Network error: {str(e)}")
    
    async def domain_search(self, domain: str, limit: int = 10) -> Dict[str, Any]:
        """Search for email addresses associated with a domain"""
        params = {"domain": domain, "limit": limit}
        return await self._make_request("domain-search", params)
    
    async def email_finder(self, domain: str, first_name: str, last_name: str) -> Dict[str, Any]:
        """Find specific email address for a person"""
        params = {
            "domain": domain,
            "first_name": first_name,
            "last_name": last_name
        }
        return await self._make_request("email-finder", params)
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information and credit balance"""
        return await self._make_request("account", {})
    
    async def email_count(self, domain: str) -> Dict[str, Any]:
        """Get count of available emails for a domain (free call)"""
        params = {"domain": domain}
        return await self._make_request("email-count", params)

# Web Scraping Functions
class WebScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def search_yellow_pages(self, query: str, location: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Search Yellow Pages for DVD stores"""
        stores = []
        try:
            # Yellow Pages search URL
            url = f"https://www.yellowpages.com/search"
            params = {
                'search_terms': query,
                'geo_location_terms': location
            }
            
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return stores
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Parse search results
            results = soup.find_all('div', class_='result')
            
            for result in results[:max_results]:
                try:
                    name_elem = result.find('a', class_='business-name')
                    name = name_elem.text.strip() if name_elem else "Unknown"
                    
                    address_elem = result.find('div', class_='street-address')
                    address = address_elem.text.strip() if address_elem else None
                    
                    city_elem = result.find('div', class_='locality')
                    city = city_elem.text.strip() if city_elem else None
                    
                    phone_elem = result.find('div', class_='phones')
                    phone = phone_elem.text.strip() if phone_elem else None
                    
                    website_elem = result.find('a', class_='track-visit-website')
                    website = website_elem.get('href') if website_elem else None
                    
                    stores.append({
                        'name': name,
                        'address': address,
                        'city': city,
                        'phone': phone,
                        'website': website,
                        'source': 'yellow_pages',
                        'source_url': response.url
                    })
                    
                except Exception as e:
                    logger.warning(f"Error parsing result: {e}")
                    continue
            
            # Add delay to be respectful
            time.sleep(random.uniform(1, 3))
            
        except Exception as e:
            logger.error(f"Error searching Yellow Pages: {e}")
        
        return stores
    
    def search_yelp(self, query: str, location: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Search Yelp for DVD stores"""
        stores = []
        try:
            # Note: This is a simplified scraper. In production, you'd use Yelp's API
            url = f"https://www.yelp.com/search"
            params = {
                'find_desc': query,
                'find_loc': location
            }
            
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return stores
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Parse Yelp results (simplified - actual structure may vary)
            results = soup.find_all('div', attrs={'data-testid': 'serp-ia-card'})
            
            for result in results[:max_results]:
                try:
                    name_elem = result.find('a', attrs={'data-analytics-label': 'biz-name'})
                    name = name_elem.text.strip() if name_elem else "Unknown"
                    
                    # Extract other information as available
                    stores.append({
                        'name': name,
                        'source': 'yelp',
                        'source_url': response.url
                    })
                    
                except Exception as e:
                    logger.warning(f"Error parsing Yelp result: {e}")
                    continue
            
            time.sleep(random.uniform(1, 3))
            
        except Exception as e:
            logger.error(f"Error searching Yelp: {e}")
        
        return stores
    
    def search_reddit(self, query: str, max_posts: int = 100) -> List[Dict[str, Any]]:
        """Search Reddit for DVD store discussions"""
        stores = []
        try:
            # Reddit search URL
            url = f"https://www.reddit.com/search.json"
            params = {
                'q': query,
                'limit': max_posts,
                'sort': 'relevance'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return stores
            
            data = response.json()
            
            for post in data.get('data', {}).get('children', []):
                try:
                    post_data = post.get('data', {})
                    title = post_data.get('title', '')
                    selftext = post_data.get('selftext', '')
                    url = post_data.get('url', '')
                    
                    # Extract potential store names and information
                    text = f"{title} {selftext}"
                    
                    # Simple pattern matching for store names
                    store_patterns = [
                        r'([A-Z][a-z]+ (?:DVD|Video|Movies?|Records?)(?:\s+(?:Store|Shop|Outlet))?)',
                        r'([A-Z][a-z]+\'s (?:DVD|Video|Movies?|Records?))',
                    ]
                    
                    for pattern in store_patterns:
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        for match in matches:
                            stores.append({
                                'name': match.strip(),
                                'source': 'reddit',
                                'source_url': f"https://reddit.com{post_data.get('permalink', '')}",
                                'notes': f"Found in Reddit post: {title[:100]}..."
                            })
                
                except Exception as e:
                    logger.warning(f"Error parsing Reddit post: {e}")
                    continue
            
            time.sleep(random.uniform(1, 3))
            
        except Exception as e:
            logger.error(f"Error searching Reddit: {e}")
        
        return stores

# Global instances
hunter_client = HunterAPIClient()
web_scraper = WebScraper()
active_jobs = {}

# Background job processing
async def process_search_job(job_id: str):
    """Process a search job in the background"""
    try:
        # Get job from database
        job_doc = await db.search_jobs.find_one({"id": job_id})
        if not job_doc:
            return
        
        job = SearchJob(**job_doc)
        
        # Update status to running
        await db.search_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "running"}}
        )
        
        results = {"stores": [], "total_found": 0, "credits_used": 0}
        
        if job.job_type == "directory_search":
            # Search business directories
            query = job.parameters.get("query", "DVD store")
            location = job.parameters.get("location", "United States")
            max_results = job.parameters.get("max_results", 100)
            
            # Search Yellow Pages
            yp_stores = web_scraper.search_yellow_pages(query, location, max_results // 2)
            results["stores"].extend(yp_stores)
            
            # Search Yelp
            yelp_stores = web_scraper.search_yelp(query, location, max_results // 2)
            results["stores"].extend(yelp_stores)
            
        elif job.job_type == "reddit_search":
            # Search Reddit
            query = job.parameters.get("query", "DVD store recommendations")
            max_posts = job.parameters.get("max_posts", 100)
            
            reddit_stores = web_scraper.search_reddit(query, max_posts)
            results["stores"].extend(reddit_stores)
        
        elif job.job_type == "email_discovery":
            # Discover emails for existing stores
            store_ids = job.parameters.get("store_ids", [])
            
            for store_id in store_ids:
                try:
                    store_doc = await db.dvd_stores.find_one({"id": store_id})
                    if store_doc and store_doc.get("website"):
                        website = store_doc["website"]
                        domain = website.replace("http://", "").replace("https://", "").replace("www.", "").split("/")[0]
                        
                        # Try to find emails
                        try:
                            search_result = await hunter_client.domain_search(domain, limit=5)
                            emails = search_result.get("data", {}).get("emails", [])
                            
                            if emails:
                                best_email = emails[0]  # Take the first/best email
                                await db.dvd_stores.update_one(
                                    {"id": store_id},
                                    {
                                        "$set": {
                                            "email": best_email.get("value"),
                                            "email_confidence": best_email.get("confidence", 0) / 100,
                                            "updated_at": datetime.utcnow()
                                        }
                                    }
                                )
                                results["credits_used"] += 1
                        
                        except Exception as e:
                            logger.warning(f"Failed to find email for {domain}: {e}")
                            
                        # Add delay between requests
                        await asyncio.sleep(1)
                
                except Exception as e:
                    logger.warning(f"Error processing store {store_id}: {e}")
        
        # Store found stores in database
        for store_data in results["stores"]:
            try:
                store = DVDStore(**store_data)
                existing = await db.dvd_stores.find_one({"name": store.name, "city": store.city})
                if not existing:
                    await db.dvd_stores.insert_one(store.dict())
                    results["total_found"] += 1
            except Exception as e:
                logger.warning(f"Error storing store: {e}")
        
        # Update job completion
        await db.search_jobs.update_one(
            {"id": job_id},
            {
                "$set": {
                    "status": "completed",
                    "results": results,
                    "completed_at": datetime.utcnow(),
                    "stores_found": results["total_found"],
                    "credits_used": results["credits_used"]
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}")
        await db.search_jobs.update_one(
            {"id": job_id},
            {
                "$set": {
                    "status": "failed",
                    "error_message": str(e),
                    "completed_at": datetime.utcnow()
                }
            }
        )
    
    finally:
        if job_id in active_jobs:
            del active_jobs[job_id]

# API Routes
@api_router.get("/")
async def root():
    return {"message": "DVD Store Data Collection API"}

@api_router.get("/hunter/account")
async def get_hunter_account():
    """Get Hunter.io account information"""
    try:
        result = await hunter_client.get_account_info()
        return {
            "account_info": result.get("data", {}),
            "credits_remaining": result.get("data", {}).get("calls", {}).get("left", 0),
            "plan_name": result.get("data", {}).get("plan_name", "unknown")
        }
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/stores", response_model=DVDStore)
async def create_store(store: DVDStoreCreate):
    """Create a new DVD store entry"""
    store_dict = store.dict()
    store_obj = DVDStore(**store_dict)
    await db.dvd_stores.insert_one(store_obj.dict())
    return store_obj

@api_router.get("/stores", response_model=List[DVDStore])
async def get_stores(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    verified: Optional[bool] = Query(None)
):
    """Get DVD stores with filtering and pagination"""
    filter_dict = {}
    
    if search:
        filter_dict["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"city": {"$regex": search, "$options": "i"}},
            {"address": {"$regex": search, "$options": "i"}}
        ]
    
    if state:
        filter_dict["state"] = state
    
    if verified is not None:
        filter_dict["verified"] = verified
    
    stores = await db.dvd_stores.find(filter_dict).skip(skip).limit(limit).to_list(limit)
    return [DVDStore(**store) for store in stores]

@api_router.put("/stores/{store_id}", response_model=DVDStore)
async def update_store(store_id: str, store_update: DVDStoreCreate):
    """Update a DVD store"""
    update_dict = store_update.dict(exclude_unset=True)
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await db.dvd_stores.find_one_and_update(
        {"id": store_id},
        {"$set": update_dict},
        return_document=True
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return DVDStore(**result)

@api_router.delete("/stores/{store_id}")
async def delete_store(store_id: str):
    """Delete a DVD store"""
    result = await db.dvd_stores.delete_one({"id": store_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")
    return {"message": "Store deleted successfully"}

@api_router.post("/stores/{store_id}/verify")
async def verify_store(store_id: str):
    """Mark a store as verified"""
    result = await db.dvd_stores.find_one_and_update(
        {"id": store_id},
        {"$set": {"verified": True, "updated_at": datetime.utcnow()}},
        return_document=True
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return DVDStore(**result)

@api_router.post("/search/directory")
async def start_directory_search(
    background_tasks: BackgroundTasks,
    query: str = "DVD store",
    location: str = "United States",
    max_results: int = 100
):
    """Start a directory search job"""
    job = SearchJob(
        job_type="directory_search",
        parameters={
            "query": query,
            "location": location,
            "max_results": max_results
        }
    )
    
    await db.search_jobs.insert_one(job.dict())
    
    # Start background processing
    task = asyncio.create_task(process_search_job(job.id))
    active_jobs[job.id] = task
    
    return {"job_id": job.id, "status": "started"}

@api_router.post("/search/reddit")
async def start_reddit_search(
    background_tasks: BackgroundTasks,
    query: str = "DVD store recommendations",
    max_posts: int = 100
):
    """Start a Reddit search job"""
    job = SearchJob(
        job_type="reddit_search",
        parameters={
            "query": query,
            "max_posts": max_posts
        }
    )
    
    await db.search_jobs.insert_one(job.dict())
    
    # Start background processing
    task = asyncio.create_task(process_search_job(job.id))
    active_jobs[job.id] = task
    
    return {"job_id": job.id, "status": "started"}

@api_router.post("/search/emails")
async def start_email_discovery(
    background_tasks: BackgroundTasks,
    store_ids: Optional[List[str]] = None
):
    """Start email discovery for stores"""
    if not store_ids:
        # Get all stores without emails
        stores = await db.dvd_stores.find({"email": None, "website": {"$ne": None}}).to_list(1000)
        store_ids = [store["id"] for store in stores]
    
    job = SearchJob(
        job_type="email_discovery",
        parameters={"store_ids": store_ids}
    )
    
    await db.search_jobs.insert_one(job.dict())
    
    # Start background processing
    task = asyncio.create_task(process_search_job(job.id))
    active_jobs[job.id] = task
    
    return {"job_id": job.id, "status": "started", "stores_to_process": len(store_ids)}

@api_router.get("/jobs", response_model=List[SearchJob])
async def get_search_jobs(limit: int = Query(50, ge=1, le=100)):
    """Get search jobs"""
    jobs = await db.search_jobs.find().sort("created_at", -1).limit(limit).to_list(limit)
    return [SearchJob(**job) for job in jobs]

@api_router.get("/jobs/{job_id}", response_model=SearchJob)
async def get_search_job(job_id: str):
    """Get a specific search job"""
    job = await db.search_jobs.find_one({"id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return SearchJob(**job)

@api_router.get("/stats")
async def get_stats():
    """Get database statistics"""
    total_stores = await db.dvd_stores.count_documents({})
    verified_stores = await db.dvd_stores.count_documents({"verified": True})
    stores_with_emails = await db.dvd_stores.count_documents({"email": {"$ne": None}})
    active_job_count = len(active_jobs)
    
    # Get recent jobs
    recent_jobs = await db.search_jobs.find().sort("created_at", -1).limit(5).to_list(5)
    
    # Get Hunter account info
    try:
        hunter_info = await hunter_client.get_account_info()
        credits_remaining = hunter_info.get("data", {}).get("calls", {}).get("left", 0)
    except:
        credits_remaining = "unknown"
    
    return {
        "total_stores": total_stores,
        "verified_stores": verified_stores,
        "stores_with_emails": stores_with_emails,
        "active_jobs": active_job_count,
        "credits_remaining": credits_remaining,
        "recent_jobs": recent_jobs
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()