import requests
from bs4 import BeautifulSoup
import re
import csv
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configure Selenium
def get_selenium_driver():
    options = Options()
    options.add_argument("--headless")  # Run in headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--user-agent=Mozilla/5.0")
    return webdriver.Chrome(options=options)

# Selenium-based extraction
def extract_contact_info_selenium(url):
    try:
        driver = get_selenium_driver()
        driver.get(url)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', soup.text))
        raw_phones = set(re.findall(r'\b\d{7,10}\b', soup.text))
        valid_phones = {num for num in raw_phones if len(num) in [10, 13] and (num.startswith("98") or num.startswith("01") or "+977" in num)}
        social_links = {link['href'] for link in soup.find_all('a', href=True) if any(domain in link['href'] for domain in ['facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com'])}

        driver.quit()
        return {"emails": emails, "phones": valid_phones, "social_links": social_links}
    except Exception as e:
        logging.error(f"Selenium error for {url}: {e}")
        return {"emails": set(), "phones": set(), "social_links": set()}
    finally:
        driver.quit()

# Requests-based extraction
def extract_contact_info(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, timeout=8, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', soup.text))
            raw_phones = set(re.findall(r'\b\d{7,10}\b', soup.text))
            valid_phones = {num for num in raw_phones if len(num) in [10, 13] and (num.startswith("98") or num.startswith("01") or "+977" in num)}
            social_links = {link['href'] for link in soup.find_all('a', href=True) if any(domain in link['href'] for domain in ['facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com'])}

            return {"emails": emails, "phones": valid_phones, "social_links": social_links}
        else:
            logging.warning(f"Request failed for {url} with status {response.status_code}")
            return extract_contact_info_selenium(url)  # Fallback to Selenium
    except Exception as e:
        logging.error(f"Requests error for {url}: {e}")
        return extract_contact_info_selenium(url)

# Validate extracted data
def validate_extraction_data(data, url):
    if not data["emails"] and not data["phones"] and not data["social_links"]:
        logging.warning(f"No contact data extracted from {url}")
    else:
        logging.info(f"Extracted from {url}: Emails: {data['emails']}, Phones: {data['phones']}, Social Links: {data['social_links']}")

# Process a single URL
def process_url(base_url, crawled_urls, results, max_depth=2):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(base_url, timeout=8, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            links = [urljoin(base_url, a['href']) for a in soup.find_all('a', href=True)]
            links = [link for link in links if urlparse(link).netloc]
            for link in links[:max_depth]:
                if link not in crawled_urls:
                    crawled_urls.add(link)
                    contact_info = extract_contact_info(link)
                    validate_extraction_data(contact_info, link)
                    results.append(contact_info)
        else:
            logging.warning(f"Failed to access {base_url} (Status: {response.status_code})")
    except Exception as e:
        logging.error(f"Error accessing {base_url}: {e}")

# Crawl websites
def crawl_websites(base_urls, max_depth=2):
    crawled_urls = set()
    results = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(lambda url: process_url(url, crawled_urls, results, max_depth), base_urls)

    return results

# Search websites
def search_websites_with_keywords(keywords):
    search_urls = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for keyword in keywords:
        query = "+".join(keyword.split())
        google_search_url = f"https://www.google.com/search?q={query}"
        try:
            response = requests.get(google_search_url, headers=headers, timeout=8)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if "/url?q=" in href and "webcache" not in href:
                        extracted_url = href.split("/url?q=")[1].split("&")[0]
                        search_urls.append(extracted_url)
            else:
                logging.warning(f"Search failed for '{keyword}' (Status: {response.status_code})")
        except Exception as e:
            logging.error(f"Search error for '{keyword}': {e}")
    return list(set(search_urls))

if __name__ == "__main__":
    keywords = [
        "Japanese School",
        "Nihongo",
        "ɲihoŋɡo",
        "Hiroshima Japanese Language School",
        "Japanese Language Institutions In Japan",
        "Japanese Language Schools of Japan"
    ]
    websites = search_websites_with_keywords(keywords)
    if not websites:
        logging.error("No websites found. Please check the keywords or internet connectivity.")
    else:
        logging.info(f"Found websites: {websites}")

        crawled_data = crawl_websites(websites)
        if crawled_data:
            with open("Japanese-Language_Details.csv", "w", newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Email", "Phone", "Social Media Links"])
                for entry in crawled_data:
                    emails = ", ".join(entry["emails"]) if entry["emails"] else "N/A"
                    phones = ", ".join(entry["phones"]) if entry["phones"] else "N/A"
                    social_links = ", ".join(entry["social_links"]) if entry["social_links"] else "N/A"
                    writer.writerow([emails, phones, social_links])
            logging.info("Data saved to Japanese-Language_Details.csv")
        else:
            logging.warning("No data crawled from the websites.")
