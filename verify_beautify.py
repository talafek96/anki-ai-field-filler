
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path("src").resolve()))

import bs4
from core.filler import Filler

def test_beautification():
    messy_html = "<div><p>Hello</p><ul><li>Item 1</li><li>Item 2</li></ul></div>"
    expected_contains = "  <li>\n   Item 1\n  </li>" # Indentation varies by bs4 version but generally has newlines
    
    result = Filler._to_html(messy_html)
    print("--- Original ---")
    print(messy_html)
    print("--- Beautified ---")
    print(result)
    
    if "<li>" in result and "\n" in result:
        print("SUCCESS: HTML contains newlines/indentation.")
    else:
        print("FAILURE: HTML does not seem beautified.")

def test_plain_text():
    text = "Line 1\nLine 2"
    result = Filler._to_html(text)
    print("--- Text ---")
    print(text)
    print("--- Result ---")
    print(result)
    
    if result == "Line 1<br>Line 2":
        print("SUCCESS: Plain text converted correctly.")
    else:
        print("FAILURE: Plain text conversion failed.")

if __name__ == "__main__":
    test_beautification()
    test_plain_text()
