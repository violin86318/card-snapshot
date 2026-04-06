from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="card-snapshot",
    version="1.0.0",
    author="violin86318",
    author_email="pommotion.com@gmail.com",
    description="智能从网页中导出卡片元素为 PNG 图片",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/violin86318/card-snapshot",
    py_modules=["card_snapshot"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "playwright>=1.40.0",
    ],
    entry_points={
        "console_scripts": [
            "card-snapshot=card_snapshot:main",
        ],
    },
)
