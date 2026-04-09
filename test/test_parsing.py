"""파서 테스트 python -m test.test_parsing"""
from src.parse.parser import DoclingParser

def main():
    parser = DoclingParser(overlap_threshold=0.15, containment_threshold=0.15)
    file_path = "data/회계_sample.pdf"  

    parsed_doc = parser.parse(file_path)
    md_file = parsed_doc.text
    with open("data/회계_sample.md", "w") as f:
        f.write(md_file)
if __name__ == "__main__":
    main()