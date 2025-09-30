import os
import argparse
import re
from pathlib import Path
from html_to_markdown import convert_to_markdown as md  # New library
from bs4 import BeautifulSoup, NavigableString
from notes_export_utils import get_tracker


def fix_html_entities(html_content: str) -> str:
    """Fix incomplete HTML entities and normalize whitespace"""
    # html_content = html_content.replace('&quot', '&quot;')
    # html_content = html_content.replace('&amp', '&amp;')
    # html_content = html_content.replace('&lt', '&lt;')
    # html_content = html_content.replace('&gt', '&gt;')
    # Normalize multiple &nbsp; and spaces to prevent codeblocks
    # html_content = re.sub(r'(&nbsp;|\s)+', ' ', html_content)
    # Strip leading/trailing spaces in divs
    # html_content = re.sub(r'<div>\s+', '<div>', html_content)
    # html_content = re.sub(r'\s+</div>', '</div>', html_content)
    return html_content


def normalize_indentation(soup: BeautifulSoup) -> BeautifulSoup:
    """Convert indented <div> tags to <li> within <ul> and remove empty <li> tags"""
    # Remove empty <li> tags (e.g., <li><br/></li>)
    for li in soup.find_all('li'):
        if li.find('br') and not li.get_text(strip=True):
            li.decompose()

    # Track current list context
    current_ul = None
    for ul in soup.find_all('ul', class_='Apple-dash-list'):
        current_ul = ul  # Last <ul> encountered
        break  # Use the first top-level list for simplicity

    # Process <div> tags
    for div in soup.find_all('div'):
        if div.string and div.string.strip():
            # Estimate indentation from spaces or styles
            indent_level = 0
            if div.get('style') and 'margin-left' in div['style']:
                margin = re.search(r'margin-left:\s*(\d+)px', div.get('style', ''))
                if margin:
                    indent_level = int(int(margin.group(1)) / 20)  # ~20px per list level
            else:
                leading_spaces = len(div.string) - len(div.string.lstrip())
                indent_level = leading_spaces // 2  # 2 spaces ~ 1 level

            # Create new <li> and wrap in <ul>
            li = soup.new_tag('li')
            li.string = div.string.strip()

            if current_ul and indent_level > 0:
                # Nest within current <ul> or create new sub-<ul>
                parent = current_ul
                for _ in range(indent_level):
                    # Find or create nested <ul>
                    last_ul = parent.find('ul', recursive=False)
                    if not last_ul:
                        last_ul = soup.new_tag('ul', attrs={'class': 'Apple-dash-list'})
                        parent.append(last_ul)
                    parent = last_ul
                parent.append(li)
            else:
                # No list context or no indent, add to top-level <ul>
                if not current_ul:
                    current_ul = soup.new_tag('ul', attrs={'class': 'Apple-dash-list'})
                    soup.append(current_ul)
                current_ul.append(li)

            div.decompose()  # Remove original <div>

    return soup


def convert_html_to_md(force: bool = False):
    """Convert HTML files to Markdown using JSON tracking"""
    tracker = get_tracker()

    # Get notes to process
    if force:
        print("Force mode enabled - processing all notes regardless of export dates...")
        notes_to_process = tracker.get_all_notes()
    else:
        notes_to_process = tracker.get_notes_to_process('markdown')

    if not notes_to_process:
        print("No notes need markdown conversion - all up to date!")
        return

    print(f"Processing {len(notes_to_process)} notes for markdown conversion...")

    for note in notes_to_process:
        try:
            print(f"Converting: {note['filename']} from {note['notebook']}")

            # Read and preprocess HTML
            with open(note['source_file'], "r", encoding="utf-8") as file:
                html_content = file.read()
                #  NOTE: We already converted the Apple HTML Entities inside of the AppleScript
                # Fix Notes.app entity quirks
                html_content = fix_html_entities(html_content)
                #  TODO: decide on which HTML Parser to use
                # soup = BeautifulSoup(html_content, "html.parser")
                soup = BeautifulSoup(html_content, "lxml")
                #  TODO: is fixing indentation worth it ?
                # soup = normalize_indentation(soup)

                # Convert to Markdown with proper list indentation
                # print(f"{soup}")
                markdown_text = md(str(soup),
                                   heading_style="atx",
                                   list_indent_type="spaces",
                                   list_indent_width=4)

            # Add frontmatter for Obsidian
            frontmatter = f"---\ntags: []\ncreated: {note['note_info']['created']}\nmodified: {note['note_info']['modified']}\n---\n\n"
            markdown_text = frontmatter + markdown_text

            # Get output path
            output_file = tracker.get_output_path('md', note['notebook'], note['filename'], '.md')

            # Ensure output directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Write Markdown content
            with open(output_file, "w", encoding="utf-8") as file:
                file.write(markdown_text)

            print(f"Created: {output_file}")

            # Copy attachments if any
            tracker.copy_attachments(note['source_file'], output_file)

            # Mark as exported in JSON
            tracker.mark_note_exported(note['json_file'], note['note_id'], 'markdown')

        except Exception as e:
            print(f"Error converting {note['filename']}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert HTML to Markdown")
    parser.add_argument('--force', action='store_true', help="Force conversion of all notes, ignoring export dates")
    args = parser.parse_args()

    convert_html_to_md(force=args.force)
