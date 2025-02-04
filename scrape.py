import requests
from bs4 import BeautifulSoup
import re
import csv
from urllib.parse import urljoin, urlparse
import logging
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Function to extract contact information from a webpage
def extract_contact_info(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract emails
        emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', soup.text))

        # Extract phone numbers
        raw_phones = set(re.findall(r'\b\d{7,15}\b', soup.text))
        valid_phones = {num for num in raw_phones if len(num) in [10, 13] and (num.startswith("98") or num.startswith("01") or "+977" in num)}

        # Extract social media links
        social_links = {urljoin(url, link['href']) for link in soup.find_all('a', href=True)
                        if any(domain in link['href'] for domain in ['facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com'])}

        return {"emails": emails, "phones": valid_phones, "social_links": social_links}
    except Exception as e:
        logging.error(f"Error extracting data from {url}: {e}")
        return {"emails": set(), "phones": set(), "social_links": set()}

# Function to crawl websites and collect data
def crawl_websites(base_urls, max_depth=2):
    crawled_urls = set()
    results = []

    def process_url(base_url, depth):
        if base_url in crawled_urls or depth > max_depth:
            return
        crawled_urls.add(base_url)
        logging.info(f"Crawling URL: {base_url}")

        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(base_url, timeout=10, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract and save contact info for the current URL
            contact_info = extract_contact_info(base_url)
            results.append(contact_info)

            # Find internal links
            links = [urljoin(base_url, a['href']) for a in soup.find_all('a', href=True)]
            links = [link for link in links if urlparse(link).netloc and link not in crawled_urls]

            # Recursively process links
            for link in links:
                process_url(link, depth + 1)
        except Exception as e:
            logging.error(f"Error processing {base_url}: {e}")

    # Use multithreading for efficiency
    with ThreadPoolExecutor(max_workers=10) as executor:
        for url in base_urls:
            executor.submit(process_url, url, 1)

    return results

# Function to search Google for relevant websites
def search_websites_with_keywords(keywords):
    search_urls = []
    headers = {'User-Agent': 'Mozilla/5.0'}

    for keyword in keywords:
        try:
            search_url = f"https://www.google.com/search?q={'+'.join(keyword.split())}&num=10"
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract URLs from Google search results
            for link in soup.find_all('a', href=True):
                href = link['href']
                if "/url?q=" in href and "webcache" not in href:
                    extracted_url = href.split("/url?q=")[1].split("&")[0]
                    if extracted_url not in search_urls:
                        search_urls.append(extracted_url)
        except Exception as e:
            logging.error(f"Error during keyword search for '{keyword}': {e}")

    return list(set(search_urls))

# Main execution
if __name__ == "__main__":
    keywords = [
        "Nepal Consultancy",
        "study abroad consultancy Nepal",
        "best educational consultancy in Nepal",
        "educational consultancy in Kathmandu",
        "educational consultancy in Pokhara",
        "educational consultancy in Butwal",
        "educational consultancy in Bharatpur",
        "educational consultancy in Birgunj",
        "educational consultancy in Jhapa",
        "educational consultancy in Biratnagar",
        "educational consultancy in Nepalgunj",
        "best education consultancy in Nepal for USA",
        "best education consultancy in Nepal for Australia",
        "consultancy for abroad studies Nepal",
        "IELTS",
        "PTE",
        "consultancy for European countries",
        "Study in Japan"
    ]

    # Step 1: Search Google for websites
    websites = search_websites_with_keywords(keywords)
    logging.info(f"Found websites: {websites}")

    # Step 2: Crawl websites for contact information
    crawled_data = crawl_websites(websites)

    # Step 3: Save results to CSV
    with open("Consultancies_Details_Info.csv", "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Email", "Phone", "Social Media Links"])
        for entry in crawled_data:
            emails = ", ".join(entry["emails"]) if entry["emails"] else "N/A"
            phones = ", ".join(entry["phones"]) if entry["phones"] else "N/A"
            social_links = ", ".join(entry["social_links"]) if entry["social_links"] else "N/A"
            writer.writerow([emails, phones, social_links])

    logging.info("Data saved to Consultancies_Details_Info.csv")
