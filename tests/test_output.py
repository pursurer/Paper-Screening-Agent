"""输出交付模块测试"""
import pytest
import tempfile
import os
import csv
from src.output_generator import (
    GradedPaper,
    write_graded_csv,
    write_review_csv,
    CSV_FIELD_ORDER,
)


class TestGradedPaper:
    """测试 GradedPaper 数据类"""

    def test_graded_paper_creation(self):
        """验证 GradedPaper 创建"""
        paper = GradedPaper(
            score=8,
            relevance_tier="Strong",
            id="neurips_1",
            title="Test Paper",
            keywords='["AI", "Memory"]',
            reasoning="涉及 KV Cache 压缩",
            abstract="This is a test abstract.",
            pdf="https://example.com/paper.pdf",
            forum="https://example.com/forum",
            year=2025,
            presentation_type="Oral"
        )
        assert paper.score == 8
        assert paper.relevance_tier == "Strong"
        assert paper.reasoning == "涉及 KV Cache 压缩"

    def test_graded_paper_fields_complete(self):
        """验证 GradedPaper 数据类字段完整"""
        paper = GradedPaper(
            score=10,
            relevance_tier="Core",
            id="test_1",
            title="Title",
            keywords="[]",
            reasoning="核心相关",
            abstract="Abstract",
            pdf="pdf_url",
            forum="forum_url",
            year=2024,
            presentation_type="Poster"
        )
        assert hasattr(paper, 'score')
        assert hasattr(paper, 'relevance_tier')
        assert hasattr(paper, 'id')
        assert hasattr(paper, 'title')
        assert hasattr(paper, 'keywords')
        assert hasattr(paper, 'reasoning')
        assert hasattr(paper, 'abstract')
        assert hasattr(paper, 'pdf')
        assert hasattr(paper, 'forum')
        assert hasattr(paper, 'year')
        assert hasattr(paper, 'presentation_type')


class TestWriteGradedCSV:
    """测试主数据库 CSV 生成"""

    def test_write_graded_csv(self):
        """验证主数据库 CSV 生成"""
        papers = [
            GradedPaper(
                score=9, relevance_tier="Core", id="p1", title="Paper 1",
                keywords="[]", reasoning="核心", abstract="Abstract 1",
                pdf="pdf1", forum="forum1", year=2025, presentation_type="Oral"
            ),
            GradedPaper(
                score=6, relevance_tier="General", id="p2", title="Paper 2",
                keywords="[]", reasoning="一般", abstract="Abstract 2",
                pdf="pdf2", forum="forum2", year=2025, presentation_type="Poster"
            ),
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name
        
        try:
            write_graded_csv(papers, temp_path)
            
            with open(temp_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 2
            assert rows[0]['id'] == 'p1'
            assert rows[0]['Score'] == '9'
        finally:
            os.unlink(temp_path)

    def test_csv_field_order(self):
        """验证字段顺序正确"""
        expected_order = [
            'Score', 'Relevance_Tier', 'id', 'title', 'keywords',
            'Reasoning', 'abstract', 'pdf', 'forum', 'year', 'presentation_type'
        ]
        assert CSV_FIELD_ORDER == expected_order

    def test_csv_sorted_by_score(self):
        """验证按 Score 降序排列"""
        papers = [
            GradedPaper(
                score=5, relevance_tier="General", id="p1", title="Paper 1",
                keywords="[]", reasoning="一般", abstract="Abstract 1",
                pdf="pdf1", forum="forum1", year=2025, presentation_type="Oral"
            ),
            GradedPaper(
                score=10, relevance_tier="Core", id="p2", title="Paper 2",
                keywords="[]", reasoning="核心", abstract="Abstract 2",
                pdf="pdf2", forum="forum2", year=2025, presentation_type="Poster"
            ),
            GradedPaper(
                score=7, relevance_tier="Strong", id="p3", title="Paper 3",
                keywords="[]", reasoning="强相关", abstract="Abstract 3",
                pdf="pdf3", forum="forum3", year=2025, presentation_type="Oral"
            ),
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name
        
        try:
            write_graded_csv(papers, temp_path)
            
            with open(temp_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            scores = [int(row['Score']) for row in rows]
            assert scores == [10, 7, 5]
        finally:
            os.unlink(temp_path)

    def test_write_empty_list(self):
        """验证空论文列表生成仅含表头的 CSV"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name
        
        try:
            write_graded_csv([], temp_path)
            
            with open(temp_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 0
        finally:
            os.unlink(temp_path)


class TestWriteReviewCSV:
    """测试边界复核 CSV 生成"""

    def test_write_review_csv(self):
        """验证边界复核 CSV 生成"""
        papers = [
            GradedPaper(
                score=3, relevance_tier="Boundary", id="p1", title="Paper 1",
                keywords="[]", reasoning="边界", abstract="Abstract 1",
                pdf="pdf1", forum="forum1", year=2025, presentation_type="Oral"
            ),
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name
        
        try:
            write_review_csv(papers, temp_path)
            
            with open(temp_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 1
            assert rows[0]['Score'] == '3'
        finally:
            os.unlink(temp_path)

    def test_reasoning_with_special_chars(self):
        """验证 Reasoning 含特殊字符正确转义"""
        papers = [
            GradedPaper(
                score=8, relevance_tier="Strong", id="p1", title="Paper, with comma",
                keywords='["test"]', reasoning='理由含"引号"和,逗号',
                abstract="Abstract with\nnewline",
                pdf="pdf1", forum="forum1", year=2025, presentation_type="Oral"
            ),
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name
        
        try:
            write_graded_csv(papers, temp_path)
            
            with open(temp_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 1
            assert '引号' in rows[0]['Reasoning']
            assert '逗号' in rows[0]['Reasoning']
        finally:
            os.unlink(temp_path)
