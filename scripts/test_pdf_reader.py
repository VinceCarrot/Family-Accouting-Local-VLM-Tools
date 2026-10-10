#!/usr/bin/env python
"""
测试脚本：演示如何使用 read_pdf 和 save_images 函数

用法:
    python scripts/test_pdf_reader.py <pdf_file> [password] [output_dir]

示例:
    python scripts/test_pdf_reader.py statement.pdf
    python scripts/test_pdf_reader.py statement.pdf "123456" "/tmp/output"
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.tools.pdf_analyzer import read_pdf, save_images


def main():
    if len(sys.argv) < 2:
        print("用法: python test_pdf_reader.py <pdf_file> [password] [output_dir]")
        print("\n示例:")
        print("  python test_pdf_reader.py statement.pdf")
        print("  python test_pdf_reader.py statement.pdf '123456' '/tmp/output'")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    password = sys.argv[2] if len(sys.argv) > 2 else None
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "pdf_output"
    
    # 验证PDF文件
    if not os.path.exists(pdf_file):
        print(f"❌ PDF文件不存在: {pdf_file}")
        sys.exit(1)
    
    print(f"📄 正在读取 PDF: {pdf_file}")
    if password:
        print(f"🔑 使用密码")
    
    # 读取PDF
    images = read_pdf(pdf_file, password)
    
    if not images:
        print("❌ 读取PDF失败")
        sys.exit(1)
    
    print(f"✅ 成功读取 {len(images)} 页")
    print(f"📐 第一页大小: {images[0].size}")
    
    # 保存图片
    print(f"💾 正在保存到 {output_dir}...")
    pdf_name = os.path.splitext(os.path.basename(pdf_file))[0]
    saved_paths = save_images(images, output_dir, prefix=pdf_name)
    
    if saved_paths:
        print(f"✅ 成功保存 {len(saved_paths)} 张图片")
        print(f"\n文件列表:")
        for path in saved_paths:
            size = os.path.getsize(path)
            print(f"  - {path} ({size/1024:.1f} KB)")
    else:
        print("❌ 保存图片失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
