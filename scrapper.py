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
from selenium.common.exceptions import TimeoutException

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

# Extract information using Selenium
def extract_contact_info_selenium(url):
    try:
        driver = get_selenium_driver()
        driver.get(url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', soup.text))
        raw_phones = set(re.findall(r'\b\d{7,15}\b', soup.text))
        valid_phones = {num for num in raw_phones if len(num) in [10, 13] and (num.startswith("98") or num.startswith("01") or "+977" in num)}
        social_links = {urljoin(url, link['href']) for link in soup.find_all('a', href=True) if any(domain in link['href'] for domain in ['facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com'])}

        driver.quit()
        return {"emails": emails, "phones": valid_phones, "social_links": social_links}
    except Exception as e:
        logging.error(f"Selenium error for {url}: {e}")
        return {"emails": set(), "phones": set(), "social_links": set()}

# Extract information using Requests and BeautifulSoup
def extract_contact_info(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', soup.text))
        raw_phones = set(re.findall(r'\b\d{7,15}\b', soup.text))
        valid_phones = {num for num in raw_phones if len(num) in [10, 13] and (num.startswith("98") or num.startswith("01") or "+977" in num)}
        social_links = {urljoin(url, link['href']) for link in soup.find_all('a', href=True) if any(domain in link['href'] for domain in ['facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com'])}

        return {"emails": emails, "phones": valid_phones, "social_links": social_links}
    except requests.exceptions.RequestException as e:
        logging.warning(f"Requests error for {url}: {e}, falling back to Selenium.")
        return extract_contact_info_selenium(url)
    except Exception as e:
        logging.error(f"Unhandled error for {url}: {e}")
        return {"emails": set(), "phones": set(), "social_links": set()}

# Crawl websites for contact information
def crawl_websites(base_urls, max_depth=2):
    crawled_urls = set()
    results = []

    def process_url(base_url):
        if base_url in crawled_urls:
            return
        crawled_urls.add(base_url)
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(base_url, timeout=10, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            links = [urljoin(base_url, a['href']) for a in soup.find_all('a', href=True)]
            links = [link for link in links if urlparse(link).netloc and link not in crawled_urls]

            contact_info = extract_contact_info(base_url)
            results.append(contact_info)

            if max_depth > 1:
                for link in links[:max_depth]:
                    process_url(link)
        except Exception as e:
            logging.error(f"Error processing {base_url}: {e}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(process_url, base_urls)

    return results

# Search Google for relevant websites
def search_websites_with_keywords_selenium(keywords):
    driver = get_selenium_driver()
    search_urls = []
    try:
        for keyword in keywords:
            google_search_url = f"https://www.google.com/search?q={'+'.join(keyword.split())}"
            driver.get(google_search_url)
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            for link in soup.find_all('a', href=True):
                href = link['href']
                if "/url?q=" in href and "webcache" not in href:
                    extracted_url = href.split("/url?q=")[1].split("&")[0]
                    if extracted_url not in search_urls:
                        search_urls.append(extracted_url)
    except TimeoutException:
        logging.error("Google search timed out.")
    except Exception as e:
        logging.error(f"Error during keyword search: {e}")
    finally:
        driver.quit()

    return list(set(search_urls))

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
        "consultancy for European countries", "Study in Japan"
    ]

    websites = search_websites_with_keywords_selenium(keywords)
    logging.info(f"Found websites: {websites}")

    crawled_data = crawl_websites(websites)

    # Save results to CSV
    with open("Consultancies_Details_Info.csv", "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Email", "Phone", "Social Media Links"])
        for entry in crawled_data:
            emails = ", ".join(entry["emails"]) if entry["emails"] else "N/A"
            phones = ", ".join(entry["phones"]) if entry["phones"] else "N/A"
            social_links = ", ".join(entry["social_links"]) if entry["social_links"] else "N/A"
            writer.writerow([emails, phones, social_links])

    logging.info("Optimized data saved to Consultancies_Details_Info.csv")
