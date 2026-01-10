import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import traceback

def search_web(query: str, num_results: int = 3) -> str:
    """
    Performs a web search for the given query, scrapes the content of the top results,
    and returns the combined text. Includes detailed logging for debugging.

    Args:
        query: The search query.
        num_results: The number of top search results to process.

    Returns:
        A string containing the concatenated text content of the scraped web pages,
        or a detailed error message if the process fails.
    """
    print(f"RAG_TOOL: Starting web search for query: '{query}'")
    scraped_texts = []
    try:
        with DDGS() as ddgs:
            # Get search results (URLs and snippets)
            print(f"RAG_TOOL: Getting {num_results} search results from DuckDuckGo...")
            results = list(ddgs.text(query, max_results=num_results))
            
            if not results:
                print("RAG_TOOL_ERROR: DuckDuckGo returned no results.")
                return "Error: Web search returned no results."

            print(f"RAG_TOOL: Found {len(results)} results.")
            for i, result in enumerate(results):
                url = result.get('href')
                if not url:
                    print(f"RAG_TOOL_WARNING: Result {i+1} has no URL.")
                    continue

                print(f"RAG_TOOL:  [{i+1}/{len(results)}] Scraping URL: {url}")
                try:
                    # Fetch the page content with a timeout and a common user-agent
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                    response = requests.get(url, timeout=10, headers=headers)
                    response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

                    # Use BeautifulSoup to parse the HTML and extract text
                    soup = BeautifulSoup(response.content, 'html.parser')

                    # Remove script, style, nav, and footer elements which are usually noise
                    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                        element.decompose()

                    # Get text and clean it up
                    text = soup.get_text(separator='\n', strip=True)
                    
                    if text:
                        scraped_texts.append(f"--- Content from {url} ---\n{text}\n")
                        print(f"RAG_TOOL:    Successfully scraped and processed content from {url}.")
                    else:
                        print(f"RAG_TOOL_WARNING: No text content found at {url} after cleaning.")

                except requests.RequestException as e:
                    print(f"RAG_TOOL_ERROR: Could not fetch page {url}. Reason: {e}")
                except Exception as e:
                    print(f"RAG_TOOL_ERROR: An unexpected error occurred while processing page {url}. Reason: {e}")
                    traceback.print_exc()

        if not scraped_texts:
            print("RAG_TOOL_ERROR: Failed to scrape content from any of the search results.")
            return "Error: Could not retrieve readable content from any web pages."

        print("RAG_TOOL: Web search and scraping completed successfully.")
        return "\n".join(scraped_texts)

    except Exception as e:
        print(f"RAG_TOOL_ERROR: A critical error occurred during the DDGS search process. Reason: {e}")
        traceback.print_exc()
        return f"Error: Failed to perform web search due to a critical error: {e}"

if __name__ == '__main__':
    # Example usage for testing
    test_query = "latest treatments for Plasmodium falciparum malaria"
    print(f"--- Running test search for: '{test_query}' ---")
    content = search_web(test_query)
    print("\n--- FINAL SCRAPED CONTENT (first 2000 chars) ---")
    print(content[:2000] + "...")
