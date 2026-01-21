#!/usr/bin/env python3
"""
Simple SEO Validator - 主脚本
核心任务：像一个机器人，自动检查网页的SEO基本元素。
"""

import sys
import io
import requests
from bs4 import BeautifulSoup

def test_network_connectivity():
    """测试基本网络连接"""
    test_urls = [
        ("百度", "https://www.baidu.com", 5),
        ("腾讯", "https://www.qq.com", 5),
        ("GitHub", "https://github.com", 10),
    ]
    
    print("🔍 网络连接测试...")
    for name, url, timeout in test_urls:
        try:
            response = requests.get(url, timeout=timeout)
            print(f"  ✅ {name}: 可访问 (状态码: {response.status_code})")
        except Exception as e:
            print(f"  ❌ {name}: 不可访问 ({e})")

def fetch_and_parse(url, timeout=10):
    """获取网页并解析为BeautifulSoup对象"""
    try:
        print(f"正在获取: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
        }
        
        # 设置更保守的超时
        response = requests.get(
            url, 
            headers=headers, 
            timeout=timeout,
            verify=True  # 验证SSL证书
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"⚠️  警告: 非200状态码 ({response.status_code})")
            # 继续处理，但提醒用户
        
        # ========== 重点修改：编码处理 ==========
        # 首先尝试response.apparent_encoding（requests自动检测）
        if response.encoding:
            try:
                content = response.content.decode(response.encoding)
            except UnicodeDecodeError:
                # response.encoding可能不准确，尝试常见中文编码
                try:
                    # 对于.cn域名或中文网站，优先尝试GBK
                    if '.cn' in url or any(site in url for site in ['sina', 'baidu', 'sohu', '163', 'qq']):
                        content = response.content.decode('gbk')
                    else:
                        content = response.content.decode('utf-8')
                except UnicodeDecodeError:
                    # 最后回退到text属性（requests自动处理）
                    content = response.text
        else:
            # 没有encoding信息时
            import chardet
            detected = chardet.detect(response.content[:1024])  # 只检测前1KB加速
            
            # 如果置信度高，使用检测结果
            if detected['confidence'] > 0.8:
                encoding = detected['encoding']
                try:
                    content = response.content.decode(encoding, errors='ignore')
                except:
                    # 检测到的编码失败，尝试常见编码
                    content = fallback_decode(response.content, url)
            else:
                # 置信度低，直接使用后备方案
                content = fallback_decode(response.content, url)
        
        return BeautifulSoup(content, 'html.parser')
        
    except requests.exceptions.Timeout:
        print(f"❌ 超时: 连接在{timeout}秒后超时")
        print("建议: 尝试增加超时时间或检查网络连接")
        return None
        
    except requests.exceptions.SSLError:
        print("❌ SSL证书验证失败")
        print("建议: 尝试使用 verify=False（不推荐用于生产）")
        return None
        
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 连接错误: {e}")
        print("可能原因:")
        print("  1. 网站被屏蔽或无法访问")
        print("  2. 网络连接问题")
        print("  3. DNS解析失败")
        return None
        
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return None

def fallback_decode(content, url=None):
    """
    后备解码方案：按优先级尝试常见编码
    """
    # 定义解码优先级
    if url and ('.cn' in url or any(site in url for site in ['sina', 'baidu', 'sohu', '163', 'qq', 'zhihu'])):
        # 中文网站优先级
        encodings = ['gbk', 'gb2312', 'gb18030', 'utf-8', 'iso-8859-1']
    else:
        # 非中文网站优先级
        encodings = ['utf-8', 'gbk', 'gb2312', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    
    # 所有编码都失败，使用ignore错误模式
    return content.decode('utf-8', errors='ignore')

def check_initial_content(soup):
    """
    检查页面初始HTML内容是否充足，更精准地识别CSR风险
    重点检查是否包含实际的内容元素，而不仅仅是字符数
    """
    print("\n=== 检查0: 初始内容可见性（反CSR风险）===")
    
    body = soup.find('body')
    if body is None:
        print("结果: ⚠️  未找到<body>标签")
        return False
    
    # 方法1：使用deepcopy复制（需要导入copy模块）
    # import copy
    # body_copy = copy.deepcopy(body)
    
    # 方法2：更简单的方法 - 重新查找（推荐）
    # 因为我们需要修改body_copy，但保留原始body用于后续检查
    body_copy = BeautifulSoup(str(body), 'html.parser')
    
    # 方法3：或者直接使用原始body，但先备份文本
    # 先获取文本长度
    temp_body = BeautifulSoup(str(body), 'html.parser')
    
    # 移除脚本、样式、导航、页脚等非核心内容元素
    for tag in temp_body(['script', 'style', 'noscript', 'iframe', 
                         'nav', 'header', 'footer', 'aside',
                         'form', 'button', 'input']):
        tag.decompose()
    
    # 移除常见导航类元素（通过class/id判断）
    nav_selectors = ['nav', '.navigation', '.navbar', '.menu', 
                    '#nav', '#navigation', '#menu',
                    '.header', '.footer', '.sidebar']
    
    for selector in nav_selectors:
        for tag in temp_body.select(selector):
            tag.decompose()
    
    # 获取剩余文本
    visible_text = temp_body.get_text(strip=True, separator=' ')
    text_length = len(visible_text)
    word_count = len(visible_text.split())
    
    print(f"初始HTML可见文本长度: {text_length} 字符")
    print(f"大致单词数: {word_count} 词")
    
    # 核心逻辑：检查是否有实际的内容段落
    # 1. 检查是否有文章内容标签
    content_tags = body.find_all(['article', 'main'])
    # 同时检查常见的content类
    content_classes = body.find_all(class_=lambda x: x and any(
        word in str(x).lower() for word in ['content', 'post', 'article', 'main', 'entry']
    ))
    has_content_structure = len(content_tags) > 0 or len(content_classes) > 0
    
    # 2. 检查是否有实际的段落文本
    paragraphs = body.find_all('p')
    meaningful_paragraphs = [p for p in paragraphs if len(p.get_text(strip=True)) > 50]
    
    # 3. 综合判断
    if text_length < 100:  # 极少量文本
        print("结果: ❌ 风险高 - 初始HTML内容极少")
        print("说明: 该页面极可能重度依赖客户端JavaScript渲染(CSR)")
        print("影响: 搜索引擎爬虫可能无法看到您的大部分内容")
        print("建议: 确保核心内容直接包含在初始HTML中")
        return False
    
    elif text_length < 300 and len(meaningful_paragraphs) < 2:
        # 有一定文本但缺乏实质性内容段落
        print("结果: ⚠️  风险中等 - 初始HTML内容可能不足")
        print("说明: 页面可能使用了混合渲染，核心内容由JS加载")
        print("建议: 确保至少部分核心内容在初始HTML中可直接访问")
        return False
    
    elif has_content_structure or len(meaningful_paragraphs) >= 2:
        # 有内容结构或有实质性段落
        print("结果: ✅ 良好 - 初始HTML包含实质性内容")
        print("说明: 页面主要内容可能在服务器端就已渲染")
        return True
    
    else:
        # 有一定文本但不确定
        print("结果: ⚠️  需要进一步检查")
        print("说明: 页面有初始内容，但可能需要JS加载更多")
        print("提示: 对于重要页面，建议核心内容直接包含在HTML中")
        return text_length >= 200

def check_meta_description(soup):
    """
    检查页面的meta描述标签
    参考：描述页面内容、吸引点击、包含关键词、长度适中（约80字）
    """
    print("\n=== 检查2: Meta描述（Meta Description）===")
    
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    
    if not meta_desc:
        print("结果: ❌ 未找到meta描述标签")
        print("SEO影响: 搜索引擎会从页面抓取片段，无法控制搜索结果展示")
        return False
    
    desc_content = meta_desc.get('content', '').strip()
    
    if not desc_content:
        print("结果: ⚠️ meta描述内容为空")
        print("建议: 添加有意义的描述内容，吸引用户点击")
        return False
    
    desc_length = len(desc_content)
    
    # 显示部分内容（最多显示100字符）
    display_content = desc_content[:100] + ('...' if len(desc_content) > 100 else '')
    print(f"描述内容: {display_content}")
    print(f"描述长度: {desc_length} 字符")
    
    # 针对中文优化建议（中文80字≈160字符，英文150-160字符）
    chinese_count = sum(1 for char in desc_content if '\u4e00' <= char <= '\u9fff')
    is_chinese_dominant = chinese_count > len(desc_content) / 3
    
    if is_chinese_dominant:
        # 中文网站建议
        if desc_length < 50:
            print("结果: ❌ 过短 - 推荐至少80字符")
        elif desc_length < 100:
            print("结果: ⚠️  略短 - 推荐120-160字符")
        elif desc_length > 200:
            print("结果: ⚠️  过长 - 推荐不超过200字符")
        else:
            print("结果: ✅ 长度适中（适合中文网站）")
        print("推荐长度: 120-160字符（约60-80个汉字）")
    else:
        # 英文网站建议
        if desc_length < 120:
            print("结果: ❌ 过短 - 推荐至少120字符")
        elif desc_length < 140:
            print("结果: ⚠️  略短 - 推荐150-160字符")
        elif desc_length > 180:
            print("结果: ⚠️  过长 - 推荐不超过180字符")
        else:
            print("结果: ✅ 长度合适（适合英文网站）")
        print("推荐长度: 150-160字符")
    
    print("提示: 描述应包含关键词，吸引用户点击，避免与标题重复")
    return (100 <= desc_length <= 200) if is_chinese_dominant else (140 <= desc_length <= 180)

def check_title(soup):
    """
    检查页面标题（Title）
    参考：吸引人、包含关键词、长度适中（约30字）
    """
    print("\n=== 检查1: 页面标题（Title）===")
    
    title_tag = soup.find('title')
    if not title_tag:
        print("结果: ❌ 未找到<title>标签")
        print("SEO影响: 严重影响排名，搜索引擎无法确定页面主题")
        return False
    
    title_content = title_tag.get_text(strip=True)
    title_length = len(title_content)
    
    print(f"标题内容: \"{title_content}\"")
    print(f"标题长度: {title_length} 个字符")
    
    # 针对中文网站优化建议（中文约30字≈60字符，英文50-60字符）
    # 检测是否为中文（简单判断）
    chinese_count = sum(1 for char in title_content if '\u4e00' <= char <= '\u9fff')
    is_chinese_dominant = chinese_count > len(title_content) / 2
    
    if is_chinese_dominant:
        # 中文网站建议
        if title_length < 15:
            print("结果: ❌ 过短 - 推荐至少20字符")
        elif title_length < 30:
            print("结果: ⚠️  略短 - 推荐30-50字符")
        elif title_length > 70:
            print("结果: ⚠️  过长 - 推荐不超过70字符")
        else:
            print("结果: ✅ 长度适中（适合中文网站）")
        print("推荐长度: 30-50字符（约15-25个汉字）")
    else:
        # 英文/混合网站建议
        if title_length < 30:
            print("结果: ❌ 过短 - 推荐至少30字符")
        elif title_length < 50:
            print("结果: ⚠️  略短 - 推荐50-60字符")
        elif title_length > 65:
            print("结果: ⚠️  过长 - 推荐不超过65字符")
        else:
            print("结果: ✅ 长度合适（适合英文网站）")
        print("推荐长度: 50-60字符")
    
    # 检查是否包含关键词（基础检查）
    print("提示: 确保标题包含核心关键词，同时吸引点击")
    return 30 <= title_length <= 70

def check_h1(soup):
    """
    检查H1标签 - 简化但准确的版本
    重点：检查是否只有一个H1，以及是否与Title相关
    """
    print("\n=== 检查3: H1标题标签 ===")
    
    h1_tags = soup.find_all('h1')
    h1_count = len(h1_tags)
    
    print(f"找到的H1标签数量: {h1_count}")
    
    # 获取页面标题
    title_tag = soup.find('title')
    page_title = title_tag.get_text(strip=True) if title_tag else ""
    
    if h1_count == 0:
        print("结果: ❌ 未找到H1标签")
        print("\nSEO影响:")
        print("• 搜索引擎难以确定页面核心主题")
        print("• 可能降低页面在相关搜索中的排名")
        print("\n最佳实践:")
        print("• 每页应有且仅有一个H1标签")
        print("• H1通常和页面标题(Title)意思一致或接近")
        print("• H1概括页面核心主题")
        return False
    
    # 检查每个H1的内容
    h1_contents = []
    for i, h1 in enumerate(h1_tags, 1):
        h1_text = h1.get_text(strip=True)
        h1_length = len(h1_text)
        h1_contents.append(h1_text)
        
        print(f"\nH1-{i}:")
        print(f"  内容: \"{h1_text}\"")
        print(f"  长度: {h1_length} 字符")
        
        if h1_length == 0:
            print(f"  状态: ❌ 内容为空")
        elif h1_length < 10:
            print(f"  状态: ⚠️  可能过短")
        elif h1_length > 100:
            print(f"  状态: ⚠️  可能过长")
        else:
            print(f"  状态: ✅ 长度合适")
    
    # 多H1检查
    if h1_count > 1:
        print(f"\n结果: ⚠️  发现{h1_count}个H1标签")
        print("建议: 通常一个页面应该只有一个H1作为主标题")
        print("参考: 原文提到'每页只用一个'H1标签")
    
    # 与Title的关系检查（重点修改部分）
    if page_title and h1_count >= 1:
        primary_h1 = h1_contents[0]  # 第一个H1通常是最重要的
        
        print(f"\n🔗 H1与Title关联性分析:")
        print(f"  页面Title: \"{page_title}\"")
        print(f"  主H1标签: \"{primary_h1}\"")
        
        # 新的检查逻辑：判断是否"意思一致或接近"
        
        # 1. 直接相同或包含（明确相关）
        if primary_h1 == page_title:
            print(f"  关系: ⚠️ 完全相同")
            print("  提示: 可以略有不同以覆盖更多关键词")
        elif primary_h1 in page_title or page_title in primary_h1:
            print(f"  关系: ✅ 包含关系（良好）")
        
        # 2. 共享核心关键词（意思接近）
        else:
            # 简单提取可能的核心词
            def extract_key_phrases(text):
                """简单提取可能的关键短语"""
                phrases = []
                # 移除常见停用词
                stop_words = {'的', '和', '与', '及', '或', '在', '是', '有', '了', '吗', '呢', '吧', '啊'}
                words = [word for word in text if word not in stop_words]
                # 取前3-5个非停用词作为关键短语候选
                if len(words) > 2:
                    phrases.append(''.join(words[:min(3, len(words))]))
                if len(words) > 4:
                    phrases.append(''.join(words[2:min(5, len(words))]))
                return phrases
            
            h1_phrases = extract_key_phrases(primary_h1)
            title_phrases = extract_key_phrases(page_title)
            
            # 检查是否有重叠的短语
            related = False
            for h1_phrase in h1_phrases:
                for title_phrase in title_phrases:
                    if len(h1_phrase) >= 2 and len(title_phrase) >= 2:
                        # 检查是否有重叠部分
                        if h1_phrase in title_phrase or title_phrase in h1_phrase:
                            print(f"  关系: ✅ 意思接近（共享: '{h1_phrase}'/'{title_phrase}'）")
                            related = True
                            break
                if related:
                    break
            
            if not related:
                print(f"  关系: ⚠️  关联性较弱")
                print(f"  建议: H1应通常和页面标题意思一致或接近")
                print(f"  示例:")
                print(f"    Title: '如何学习Python编程 - 完整指南'")
                print(f"    H1:    'Python编程学习教程'")
    
    return h1_count == 1

def check_image_alt(soup):
    """
    检查图片的alt属性
    - 统计所有图片数量
    - 统计缺少alt属性的图片数量
    - 给出优化建议
    """
    print("\n=== 检查4: 图片Alt文本 ===")
    
    all_images = soup.find_all('img')
    total_images = len(all_images)
    
    if total_images == 0:
        print("结果: ℹ️ 页面中没有图片")
        print("建议: 适当添加相关图片可以提升用户体验")
        return True
    
    images_without_alt = [img for img in all_images if not img.get('alt')]
    missing_alt_count = len(images_without_alt)
    missing_percentage = (missing_alt_count / total_images) * 100 if total_images > 0 else 0
    
    print(f"图片总数: {total_images}")
    print(f"缺少Alt属性的图片数: {missing_alt_count}")
    print(f"缺失比例: {missing_percentage:.1f}%")
    
    if missing_alt_count == 0:
        print("结果: ✅ 所有图片都有alt属性")
        print("说明: 这有助于搜索引擎理解图片内容，也提升可访问性")
        return True
    elif missing_percentage < 20:
        print("结果: ⚠️ 少数图片缺少alt属性")
        print("建议: 为缺少alt的图片添加描述性文本")
    elif missing_percentage < 50:
        print("结果: ⚠️ 较多图片缺少alt属性")
        print("影响: 搜索引擎无法理解这些图片的内容")
        print("建议: 优先为核心内容图片添加alt文本")
    else:
        print("结果: ❌ 超过一半图片缺少alt属性")
        print("严重影响:")
        print("  - 搜索引擎无法理解图片内容")
        print("  - 视觉障碍用户无法获取图片信息")
        print("  - 错失图片搜索的流量机会")
        print("建议: 系统性地为所有图片添加alt属性")
    
    # 显示一些缺少alt的图片示例
    if missing_alt_count > 0:
        print("\n缺少alt的图片示例:")
        for i, img in enumerate(images_without_alt[:5], 1):
            src = img.get('src', '无src属性')[:50]
            print(f"  图片{i}: src='{src}...'")
    
    return missing_alt_count == 0

def check_canonical(soup, current_url):
    """
    检查规范链接标签（Canonical）
    参考：避免重复内容，指定官方版本URL
    """
    print("\n=== 检查5: Canonical标签 ===")
    
    canonical_tag = soup.find('link', attrs={'rel': 'canonical'})
    
    if not canonical_tag:
        print("结果: ⚠️ 未找到Canonical标签")
        print("影响: 可能导致重复内容问题，分散页面权重")
        print("建议: 为每个页面添加Canonical标签，指向规范URL")
        return False
    
    canonical_url = canonical_tag.get('href', '').strip()
    
    if not canonical_url:
        print("结果: ❌ Canonical标签href属性为空")
        return False
    
    print(f"Canonical URL: {canonical_url}")
    
    # 检查是否自指向（最佳实践）
    from urllib.parse import urlparse
    
    def normalize_url(url):
        """简单规范化URL用于比较"""
        parsed = urlparse(url)
        # 移除末尾斜杠和协议
        return parsed.netloc + parsed.path.rstrip('/')
    
    current_normalized = normalize_url(current_url)
    canonical_normalized = normalize_url(canonical_url)
    
    if current_normalized == canonical_normalized:
        print("结果: ✅ Canonical标签正确（自指向）")
        print("说明: 正确指定了本页面的规范URL")
        return True
    else:
        print("结果: ⚠️ Canonical指向其他URL")
        print("影响: 本页面可能不是规范版本")
        print("建议: 确保重要页面指向自身作为规范版本")
        return False

def main(url):
    """主函数"""
    # 如果是特定不可访问的网站，直接提示
    blocked_sites = [
        'bbc.com',
        'wikipedia.org',
        'twitter.com',
        'facebook.com',
        'google.com',
        'youtube.com',
    ]
    
    for site in blocked_sites:
        if site in url.lower():
            print(f"⚠️  注意: {site} 在国内可能无法直接访问")
            print("建议使用以下网站测试:")
            print("  - https://www.baidu.com")
            print("  - https://www.qq.com")
            print("  - https://www.jd.com")
            print("  - https://www.taobao.com")
            print("  - https://www.zhihu.com")
            answer = input("是否继续尝试? (y/n): ")
            if answer.lower() != 'y':
                return

    print(f"🔍 开始SEO分析: {url}")
    print("=" * 50)
    
    # 第一步：获取并解析网页
    soup = fetch_and_parse(url)
    if soup is None:
        print("\n无法获取网页内容，检查:")
        print("1. 网络连接是否正常")
        print("2. 网址是否正确")
        print("3. 网站是否可访问")
        print("\n推荐测试网址:")
        print("https://www.baidu.com")
        print("https://www.qq.com")
        print("https://www.zhihu.com")
        return
    
    # 第二步：执行各项检查
    # 先做“内容可见性”基础检查
    is_content_visible = check_initial_content(soup)
    # 根据结果，可选择性给出提示
    if not is_content_visible:
        print("\n提示: 由于初始内容不足，以下部分检查结果可能不准确或无法进行。")
    
    # 再进行其他具体检查
    check_title(soup)
    check_meta_description(soup)  
    check_h1(soup)
    check_image_alt(soup)
    check_canonical(soup, url)
    
    print("\n" + "="*40)
    print("基础检查完成。")
    print("=" * 40)

if __name__ == "__main__":
    # 处理命令行参数
    if len(sys.argv) < 2:
        print("使用方法: python validator.py <网址>")
        print("示例: python validator.py https://www.example.com")
        sys.exit(1)
    
    # 启动
    main(sys.argv[1])
