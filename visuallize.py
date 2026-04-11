import sys
from pathlib import Path

from PIL import Image, ImageDraw
from docling_core.transforms.visualizer.layout_visualizer import LayoutVisualizer
from docling_core.transforms.visualizer.reading_order_visualizer import (
    ReadingOrderVisualizer,
)

from src.parse.layout_config import create_converter
from src.parse.reading_order import reorder_reading_order

LABEL_HEIGHT = 40
GAP = 20


def _combine_three(before: Image.Image, after: Image.Image, layout: Image.Image) -> Image.Image:
    """before / after / layout 3개 이미지를 가로로 합쳐서 한 페이지 이미지로 반환"""
    w = max(before.width, after.width, layout.width)
    h = max(before.height, after.height, layout.height)
    canvas_w = w * 3 + GAP * 4
    canvas_h = h + LABEL_HEIGHT + GAP * 2
    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")

    draw = ImageDraw.Draw(canvas)
    labels = ["Before (기본)", "After (XY-Cut)", "Layout Only"]
    for i, (img, label) in enumerate(zip([before, after, layout], labels)):
        x = GAP + i * (w + GAP)
        draw.text((x + w // 2, GAP // 2), label, fill="black", anchor="mt")
        canvas.paste(img, (x, LABEL_HEIGHT + GAP))

    return canvas


def visualize(file_path: str, out_dir: str = "data/viz_output") -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 파싱 (page image 포함)
    converter = create_converter(
        overlap_threshold=0.15,
        containment_threshold=0.15,
        generate_page_images=True,
    )
    result = converter.convert(str(file_path))
    doc = result.document

    stem = Path(file_path).stem

    # --- Visualizer 구성 ---
    layout_viz = LayoutVisualizer()
    ro_viz = ReadingOrderVisualizer(
        base_visualizer=layout_viz,
        params=ReadingOrderVisualizer.Params(show_branch_numbering=True),
    )

    # --- BEFORE: Docling 기본 reading order ---
    before_images = ro_viz.get_visualization(doc=doc)

    # --- XY-Cut 재정렬 ---
    doc = reorder_reading_order(doc)

    # --- AFTER: 재정렬 후 reading order ---
    after_images = ro_viz.get_visualization(doc=doc)

    # --- 레이아웃만 (reading order 화살표 없이) ---
    layout_images = layout_viz.get_visualization(doc=doc)

    # --- 페이지별로 3개 이미지를 합쳐서 하나의 PDF로 저장 ---
    page_numbers = sorted(k for k in before_images.keys() if k is not None)
    combined_pages = []
    for page_no in page_numbers:
        combined = _combine_three(
            before_images[page_no],
            after_images[page_no],
            layout_images[page_no],
        )
        combined_pages.append(combined.convert("RGB"))
        print(f"[combined] page {page_no}")

    pdf_path = out / f"{stem}_combined.pdf"
    combined_pages[0].save(
        str(pdf_path),
        save_all=True,
        append_images=combined_pages[1:],
    )
    print(f"\n완료: {pdf_path} ({len(combined_pages)} pages)")


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "data/회계_sample.pdf"
    out = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "--out" else "data/viz_output"
    visualize(pdf, out)
