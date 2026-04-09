"""
Docling 레이아웃 후처리 설정 모듈

이 모듈이 필요한 이유:
    Docling의 기본 레이아웃 분석은 일반적인 문서에 최적화되어 있습니다.
    하지만 회계 문서는 텍스트가 빽빽하고, 표가 많고, 작은 번호 기호(⑴, ㈎ 등)가
    자주 등장하기 때문에 기본 설정으로는 정확한 분석이 어렵습니다.

    이 모듈은 Docling의 내부 동작을 "몽키 패치(Monkey Patch)"로 수정하여
    회계 문서에 더 적합한 레이아웃 분석을 수행하도록 합니다.

몽키 패치(Monkey Patch)란?
    - 라이브러리의 소스 코드를 직접 수정하지 않고,
      실행 중(런타임)에 특정 메서드를 다른 함수로 교체하는 기법입니다.
    - 장점: 라이브러리를 포크(fork)하거나 수정하지 않아도 동작을 바꿀 수 있음
    - 단점: 라이브러리 업데이트 시 호환성이 깨질 수 있어 주의가 필요

이 모듈에서 수행하는 패치 2가지:
    1. _remove_overlapping_clusters 패치:
       → 겹침 판단 임계값을 낮춰서, 조금만 겹쳐도 클러스터를 병합하도록 변경
    2. postprocess 패치:
       → 후처리 마지막에 리스트 마커 병합 단계를 추가
"""

import logging
from src.parse.parser_dtos import OVERLAP_THRESHOLD, CONTAINMENT_THRESHOLD
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions


# 로거 설정: 이 모듈에서 발생하는 로그 메시지를 기록합니다.
# __name__은 이 모듈의 이름(src.parse.layout_config)이 자동으로 들어갑니다.
_log = logging.getLogger(__name__)


def _patch_layout_postprocessor(
    overlap_threshold: float,
    containment_threshold: float,
):
    """
    Docling의 LayoutPostprocessor 클래스의 메서드를 몽키 패치합니다.

    왜 패치가 필요한가?
        Docling의 기본 _remove_overlapping_clusters 메서드는 겹침 임계값이 0.8입니다.
        이는 "80% 이상 겹쳐야 같은 블록으로 본다"는 뜻인데,
        회계 문서에서는 텍스트 블록이 살짝만 겹쳐도 같은 내용인 경우가 많습니다.
        그래서 임계값을 0.15(15%)로 낮추면 더 정확한 결과를 얻을 수 있습니다.

    Args:
        overlap_threshold: 겹침 판단 임계값 (0~1 사이, 낮을수록 적극적으로 병합)
        containment_threshold: 포함 판단 임계값 (0~1 사이, 낮을수록 적극적으로 병합)
    """
    # Docling 내부의 LayoutPostprocessor 클래스를 가져옵니다.
    from docling.utils.layout_postprocessor import LayoutPostprocessor

    # ──────────────────────────────────────────────────────────
    # 중복 패치 방지: 이미 패치가 적용되었으면 다시 하지 않습니다.
    # ──────────────────────────────────────────────────────────
    # hasattr()는 객체에 특정 속성이 있는지 확인하는 함수입니다.
    # "_original_remove_overlapping"이라는 속성이 이미 있다면
    # → 이전에 패치가 적용된 것이므로 바로 종료합니다.
    if hasattr(LayoutPostprocessor, "_original_remove_overlapping"):
        return

    # 패치 전에 원본 메서드를 백업해둡니다. (나중에 복원할 수 있도록)
    original = LayoutPostprocessor._remove_overlapping_clusters

    # ──────────────────────────────────────────────────────────
    # 패치 1: _remove_overlapping_clusters 교체
    # ──────────────────────────────────────────────────────────
    # 이 함수는 겹치는 클러스터(텍스트 블록)들을 찾아서 하나로 합치는 역할입니다.
    #
    # 핵심 변경점:
    #   - 원본은 내부에 하드코딩된 높은 임계값(0.8)을 사용
    #   - 패치 버전은 사용자가 지정한 낮은 임계값(_ot, _ct)을 사용
    #
    # 매개변수의 _ot, _ct에 기본값을 넣는 이유:
    #   파이썬의 클로저(closure)에서 바깥 변수를 캡처하는 방식 때문입니다.
    #   기본값으로 넣으면 함수 정의 시점의 값이 확실히 고정됩니다.
    def patched_remove(self, clusters, cluster_type, _ot=overlap_threshold, _ct=containment_threshold):
        """겹치는 클러스터를 찾아서 병합하는 패치된 버전."""

        # 빈 리스트가 들어오면 바로 반환 (처리할 클러스터가 없음)
        if not clusters:
            return []

        # ── 공간 인덱스(Spatial Index) 선택 ──
        # 공간 인덱스는 "이 영역 근처에 어떤 클러스터가 있는가?"를 빠르게 찾기 위한
        # 자료구조입니다. 클러스터 종류(일반 텍스트, 그림, 래퍼)에 따라 다른 인덱스를 사용합니다.
        spatial_index = (
            self.regular_index
            if cluster_type == "regular"
            else self.picture_index
            if cluster_type == "picture"
            else self.wrapper_index
        )

        # ── Union-Find 자료구조 생성 ──
        # Union-Find(또는 Disjoint Set)는 "어떤 것들이 같은 그룹인가?"를
        # 효율적으로 관리하는 자료구조입니다.
        #
        # 동작 원리:
        #   - 처음에는 각 클러스터가 각자 독립적인 그룹
        #   - 두 클러스터가 겹치면 union()으로 같은 그룹으로 합침
        #   - 최종적으로 같은 그룹에 속한 클러스터들을 하나로 병합
        from docling.utils.layout_postprocessor import UnionFind

        valid_clusters = {c.id: c for c in clusters}
        uf = UnionFind(valid_clusters.keys())
        params = self.OVERLAP_PARAMS[cluster_type]

        # ── 겹침 검사 루프 ──
        # 각 클러스터에 대해 주변에 겹치는 클러스터가 있는지 확인합니다.
        for cluster in clusters:
            # 공간 인덱스에서 이 클러스터의 bounding box 근처에 있는 후보를 빠르게 찾음
            candidates = spatial_index.find_candidates(cluster.bbox)
            # 유효한 클러스터만 남기고, 자기 자신은 제외
            candidates &= valid_clusters.keys()
            candidates.discard(cluster.id)

            for other_id in candidates:
                # check_overlap: 두 클러스터가 실제로 겹치는지 확인
                # _ot와 _ct가 핵심! 기본 0.8 대신 사용자가 지정한 값(예: 0.15)을 사용합니다.
                if spatial_index.check_overlap(
                    cluster.bbox,
                    valid_clusters[other_id].bbox,
                    _ot,   # overlap_threshold (겹침 비율 기준)
                    _ct,   # containment_threshold (포함 비율 기준)
                ):
                    # 겹치면 두 클러스터를 같은 그룹으로 합침
                    uf.union(cluster.id, other_id)

        # ── 그룹별 병합 ──
        # Union-Find에서 같은 그룹으로 묶인 클러스터들을 실제로 하나로 합칩니다.
        result = []
        for group in uf.get_groups().values():
            # 그룹에 클러스터가 1개뿐이면 병합할 것이 없으므로 그대로 추가
            if len(group) == 1:
                result.append(valid_clusters[group[0]])
                continue

            # 같은 그룹의 클러스터들 중 가장 "좋은" 것을 대표로 선택
            group_clusters = [valid_clusters[cid] for cid in group]
            best = self._select_best_cluster_from_group(group_clusters, params)

            # 나머지 클러스터의 셀(cell)들을 대표 클러스터에 합침
            # 셀(cell): 클러스터 안의 개별 텍스트 조각
            for cluster in group_clusters:
                if cluster != best:
                    best.cells.extend(cluster.cells)

            # 중복 셀 제거 및 정렬
            best.cells = self._deduplicate_cells(best.cells)
            best.cells = self._sort_cells(best.cells)
            result.append(best)

        return result

    # 원본 메서드를 백업하고, 패치된 버전으로 교체합니다.
    LayoutPostprocessor._original_remove_overlapping = original
    LayoutPostprocessor._remove_overlapping_clusters = patched_remove

    # ──────────────────────────────────────────────────────────
    # 패치 2: postprocess 메서드에 마커 병합 단계 추가
    # ──────────────────────────────────────────────────────────
    # 원본 postprocess가 완료된 후, 분리된 리스트 마커(⑴, ㈎ 등)를
    # 인접한 본문 클러스터에 병합하는 추가 단계를 넣습니다.
    # (cluster_merge.py의 merge_marker_clusters 함수 참고)
    original_postprocess = LayoutPostprocessor.postprocess

    def patched_postprocess(self):
        """원본 postprocess 실행 후 마커 병합을 추가로 진행합니다."""
        from src.parse.cluster_merge import merge_marker_clusters

        # 원본 후처리 실행 → 클러스터 목록과 셀 목록을 받음
        clusters, cells = original_postprocess(self)
        # 마커 클러스터를 인접 본문에 병합
        clusters = merge_marker_clusters(clusters)
        return clusters, cells

    # 이미 패치된 적이 없을 때만 적용 (중복 패치 방지)
    if not hasattr(LayoutPostprocessor, "_original_postprocess"):
        LayoutPostprocessor._original_postprocess = original_postprocess
        LayoutPostprocessor.postprocess = patched_postprocess

    # 패치 적용 완료 로그
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
    """
    커스텀 설정이 적용된 DocumentConverter를 생성합니다.

    이 함수는 다음 두 가지를 수행합니다:
        1. _patch_layout_postprocessor()로 Docling의 레이아웃 분석을 패치
        2. PDF 처리에 필요한 옵션(OCR, 표 인식 등)이 설정된 DocumentConverter 생성

    Args:
        overlap_threshold:
            클러스터 겹침 판단 기준값 (기본값: 0.15)
        containment_threshold:
            클러스터 포함 판단 기준값 (기본값: 0.15)
        generate_page_images:
            PDF의 각 페이지를 이미지로도 변환할지 여부 (기본값: True)
            True면 이미지 기반 분석도 함께 수행되어 정확도가 높아지지만,
            처리 시간과 메모리 사용량이 증가합니다.

    Returns:
        DocumentConverter: 커스텀 설정이 적용된 Docling 변환기 인스턴스
    """
    # 레이아웃 후처리 패치 적용 (프로세스 전체에서 한 번만 실행됨)
    _patch_layout_postprocessor(overlap_threshold, containment_threshold)

    # PDF 처리 파이프라인 옵션 설정
    pipeline_options = PdfPipelineOptions(
        generate_page_images=generate_page_images,  # 페이지 이미지 생성 여부
        do_table_structure=True,                     # 표 구조 인식 활성화
        do_ocr=True,                                 # OCR(광학 문자 인식) 활성화
    )

    # DocumentConverter 생성 및 반환
    # format_options에서 "pdf" 포맷에 대해 위에서 설정한 파이프라인 옵션을 적용합니다.
    return DocumentConverter(
        format_options={"pdf": PdfFormatOption(pipeline_options=pipeline_options)}
    )
