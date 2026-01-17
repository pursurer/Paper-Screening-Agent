"""论文输入解析模块测试"""
import pytest
import tempfile
import os
from src.paper_parser import Paper, parse_csv


class TestPaper:
    """测试 Paper 数据类"""

    def test_paper_creation(self):
        """验证 Paper 创建"""
        paper = Paper(
            id="neurips_1",
            title="Test Paper",
            keywords='["AI", "Memory"]',
            abstract="This is a test abstract.",
            pdf="https://example.com/paper.pdf",
            forum="https://example.com/forum",
            year=2025,
            presentation_type="Oral"
        )
        assert paper.id == "neurips_1"
        assert paper.title == "Test Paper"
        assert paper.year == 2025

    def test_paper_fields_complete(self):
        """验证 Paper 数据类字段完整"""
        paper = Paper(
            id="test_1",
            title="Title",
            keywords="[]",
            abstract="Abstract",
            pdf="pdf_url",
            forum="forum_url",
            year=2024,
            presentation_type="Poster"
        )
        assert hasattr(paper, 'id')
        assert hasattr(paper, 'title')
        assert hasattr(paper, 'keywords')
        assert hasattr(paper, 'abstract')
        assert hasattr(paper, 'pdf')
        assert hasattr(paper, 'forum')
        assert hasattr(paper, 'year')
        assert hasattr(paper, 'presentation_type')


class TestParseCSV:
    """测试 CSV 解析"""

    def test_parse_valid_csv(self):
        """验证正常 CSV 解析"""
        csv_content = '''id,title,keywords,abstract,pdf,forum,year,presentation_type
neurips_1,Test Paper,"[""AI"", ""Memory""]",This is abstract.,https://pdf.com,https://forum.com,2025,Oral
neurips_2,Another Paper,"[""RL""]",Another abstract.,https://pdf2.com,https://forum2.com,2025,Poster'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            temp_path = f.name
        
        try:
            papers = parse_csv(temp_path)
            assert len(papers) == 2
            assert papers[0].id == "neurips_1"
            assert papers[0].title == "Test Paper"
            assert papers[1].id == "neurips_2"
        finally:
            os.unlink(temp_path)

    def test_parse_empty_fields(self):
        """验证空字段处理"""
        csv_content = '''id,title,keywords,abstract,pdf,forum,year,presentation_type
neurips_1,Test Paper,,,https://pdf.com,https://forum.com,2025,Oral'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            temp_path = f.name
        
        try:
            papers = parse_csv(temp_path)
            assert len(papers) == 1
            assert papers[0].keywords == ""
            assert papers[0].abstract == ""
        finally:
            os.unlink(temp_path)

    def test_parse_keywords_json(self):
        """验证 keywords JSON 列表解析"""
        csv_content = '''id,title,keywords,abstract,pdf,forum,year,presentation_type
neurips_1,Test Paper,"[""Memory"", ""Agent"", ""LLM""]",Abstract here.,https://pdf.com,https://forum.com,2025,Oral'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            temp_path = f.name
        
        try:
            papers = parse_csv(temp_path)
            assert len(papers) == 1
            assert "Memory" in papers[0].keywords
            assert "Agent" in papers[0].keywords
        finally:
            os.unlink(temp_path)

    def test_parse_file_not_found(self):
        """验证文件不存在抛出异常"""
        with pytest.raises(FileNotFoundError):
            parse_csv("/nonexistent/path/to/file.csv")

    def test_parse_year_as_int(self):
        """验证 year 字段解析为整数"""
        csv_content = '''id,title,keywords,abstract,pdf,forum,year,presentation_type
neurips_1,Test Paper,"[]",Abstract.,https://pdf.com,https://forum.com,2025,Oral'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            temp_path = f.name
        
        try:
            papers = parse_csv(temp_path)
            assert papers[0].year == 2025
            assert isinstance(papers[0].year, int)
        finally:
            os.unlink(temp_path)
