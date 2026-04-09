"""Docling 레이아웃 후처리 설정."""

import logging
from src.parse.parser_dtos import OVERLAP_THRESHOLD, CONTAINMENT_THRESHOLD
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions


_log = logging.getLogger(__name__)


# Docling의 layout_postprocessor 로직 변경
def _patch_layout_postprocessor(
    overlap_threshold: float,
    containment_threshold: float,
):
    from docling.utils.layout_postprocessor import LayoutPostprocessor

    # 원본 보존
    if hasattr(LayoutPostprocessor, "_original_remove_overlapping"):
        return

    original = LayoutPostprocessor._remove_overlapping_clusters

    def patched_remove(self, clusters, cluster_type, _ot=overlap_threshold, _ct=containment_threshold):

        if not clusters:
            return []

        spatial_index = (
            self.regular_index
            if cluster_type == "regular"
            else self.picture_index
            if cluster_type == "picture"
            else self.wrapper_index
        )

        from docling.utils.layout_postprocessor import UnionFind

        valid_clusters = {c.id: c for c in clusters}
        uf = UnionFind(valid_clusters.keys())
        params = self.OVERLAP_PARAMS[cluster_type]

        for cluster in clusters:
            candidates = spatial_index.find_candidates(cluster.bbox)
            candidates &= valid_clusters.keys()
            candidates.discard(cluster.id)

            for other_id in candidates:
                if spatial_index.check_overlap(
                    cluster.bbox,
                    valid_clusters[other_id].bbox,
                    _ot,   # 여기가 핵심: 기본 0.8 대신 사용자 값
                    _ct,   # 여기가 핵심: 기본 0.8 대신 사용자 값
                ):
                    uf.union(cluster.id, other_id)

        result = []
        for group in uf.get_groups().values():
            if len(group) == 1:
                result.append(valid_clusters[group[0]])
                continue

            group_clusters = [valid_clusters[cid] for cid in group]
            best = self._select_best_cluster_from_group(group_clusters, params)

            for cluster in group_clusters:
                if cluster != best:
                    best.cells.extend(cluster.cells)

            best.cells = self._deduplicate_cells(best.cells)
            best.cells = self._sort_cells(best.cells)
            result.append(best)

        return result

    LayoutPostprocessor._original_remove_overlapping = original
    LayoutPostprocessor._remove_overlapping_clusters = patched_remove

    # postprocess에 마커 병합 추가
    original_postprocess = LayoutPostprocessor.postprocess

    def patched_postprocess(self):
        """원본 postprocess 실행 후 마커 병합 진행."""
        from src.parse.cluster_merge import merge_marker_clusters

        clusters, cells = original_postprocess(self)
        clusters = merge_marker_clusters(clusters)
        return clusters, cells

    if not hasattr(LayoutPostprocessor, "_original_postprocess"):
        LayoutPostprocessor._original_postprocess = original_postprocess
        LayoutPostprocessor.postprocess = patched_postprocess

    _log.info(
        f"LayoutPostprocessor patched: "
        f"overlap_threshold={overlap_threshold}, "
        f"containment_threshold={containment_threshold}, "
        f"marker_merge=enabled"
    )


def create_converter(
    overlap_threshold: float = OVERLAP_THRESHOLD,
    containment_threshold: float = CONTAINMENT_THRESHOLD,
    generate_page_images: bool = True,
) -> DocumentConverter:
    """overlap threshold가 조정된 DocumentConverter를 생성합니다."""

    # 패치 적용 (전역, 한 번만)
    _patch_layout_postprocessor(overlap_threshold, containment_threshold)

    pipeline_options = PdfPipelineOptions(
        generate_page_images=generate_page_images,
        do_table_structure=True,
        do_ocr=True,
    )

    return DocumentConverter(
        format_options={"pdf": PdfFormatOption(pipeline_options=pipeline_options)}
    )
