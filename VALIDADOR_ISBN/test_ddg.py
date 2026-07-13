import json
try:
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        results = [r for r in ddgs.text('"978-9942-581-00-6"', max_results=3)]
        print(json.dumps(results, indent=2))
except Exception as e:
    print('Error:', e)
