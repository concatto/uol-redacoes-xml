"""This spider extracts essays from Brasil Escola (http://vestibular.brasilescola.uol.com.br/banco-de-redacoes/).
"""
import scrapy
import html2text
import re
import traceback
import json
from unidecode import unidecode
from pyquery import PyQuery as pq
from bs4 import BeautifulSoup

h = html2text.HTML2Text()
h.ignore_links = True
h.ignore_images = True
h.ignore_emphasis = True
h.body_width = False

paragraph_summary = {}

IGNORE_CHAR = re.compile(r'(^[\r\n\t\s]+|[\r\n\t\s]+$)')
EXTRACT_NUMBER = re.compile(r'[^\d](\d+([.,]\d+)?).*')
PROMPT_DESCRIPTION_SUB = re.compile(r'Saiba como fazer uma boa.+', re.DOTALL)
PROMPT_INFO_SUB = re.compile(r'.+Elabore sua redação[^\r\n]+[\r\n]*', re.DOTALL)
ESSAY_COMMENTS_SUB = re.compile(r'.+Comentários do corretor', re.DOTALL)
ESSAY_COMMENTS_SUB2 = re.compile(r'Competências avaliadas.+', re.DOTALL)
ESSAY_TEXT_SUB = re.compile(r' \[[^\]~]+[\]~] ')
ESSAY_TEXT_SUB2 = re.compile(r'\[[^\]~]+[\]~]')
ESSAY_TEXT_SUB3 = re.compile(r' \[[^\]~]*[\]~]')
RED_SPAN = 'span[style*="#FF0000"]'
ORANGE_SPAN = 'span[style*="#e74c3c"]'
STRUCK_TEXT = 'strike, s'
PARENTHESIZED_CORRECTION = re.compile(r'\s*\(.+\)\s*')
PARENTHESIZED_PUNCTUATION = re.compile(r'\([.,;:]\)')
PUNCTUATION = re.compile(r'[.,;:]')
EMPTY_PARENTHESIS = '()'
CORRECTED_PUNCTUATION = re.compile(r'([.,;:])\s*\([.,;:]?\)')
CORRECTED_FULL_STOP = ' (.)'
CORRECTED_COMMA = ' (,)'
CORRECTED_SEMICOLON = ' (;)'

def select_red_spans(dom):
    return dom.select('span[style*="#FF0000"]') + dom.select('span[style*="rgb(255"]')

# Handles both tags and navigable strings.
def as_text(element):
    if element is None or element.string is None:
        return ""

    return element.string

def find_old_evidence(dom):
    for suspect in dom.select('u strong'):
        if ESSAY_TEXT_SUB2.search(as_text(suspect)):
            return True
    
    return False

def split_in_paragraphs(dom):
    print("### Going to split!")
    paragraphs = [""]
    for p in dom.select("p"):
        for child in p.descendants:
            text = as_text(child)

            if child.name == None and text != None:
                paragraphs[-1] += text

            elif child.name == 'br' and len(paragraphs[-1].strip()) > 0:
                paragraphs.append("")

        if len(paragraphs[-1].strip()) > 0:
            paragraphs.append("")

    paragraphs = list(map(lambda p: p.strip(), paragraphs))
    return paragraphs[:-1]

def strip(text):
    return IGNORE_CHAR.sub('', text)

def children_with_content(element):
    return [child for child in element.children if len(as_text(child).strip()) > 0]

def get_text(response, select):
    text = response.css(select+'::text').extract_first()
    if not text: return ''
    return strip(text)

def get_div_text(html):
    return strip(h.handle(html))

def extract_number(text):
    if text is None: return -1
    number = EXTRACT_NUMBER.findall(text)
    if len(number) == 0:
        return -1
    return float(number[0][0].replace(',', '.'))

def remove_double_breaks(text):
    text = re.sub(r'.\s+[\r\n]+', '.\n', text)
    text = re.sub(r'[\r\n]+', '\n', text)
    text = re.sub(r'(^\n+|\n+$)', '', text)
    return strip(text)

def handle_prompt_content(html):
    d = pq(html)
    if d.text() == '':
        return '', '', ''

    text = get_div_text(html)
    text = re.sub(r'^PUBLICIDADE\s*', '', text)

    description = PROMPT_DESCRIPTION_SUB.sub('', text)
    description = remove_double_breaks(strip(description))

    info = PROMPT_INFO_SUB.sub('', text)
    info = remove_double_breaks(strip(info))

    date = ''

    return description, info, date

def is_part_of_word(element, not_in_boundaries=False):
    print("Testing if part of word ", element)
    text = element.get_text()
    if not text or " " in text:
        return False # empty element or is not a single component

    prev_el = as_text(element.previous_sibling)
    next_el = as_text(element.next_sibling)
    print("Prev \"%s\"" % prev_el)
    print("Next \"%s\"" % next_el)

    part_of_prev = prev_el and prev_el[-1].isalpha() and text[0].isalpha()
    part_of_next = next_el and next_el[0].isalpha() and text[-1].isalpha()

    is_part = False
    if not_in_boundaries:
        is_part = part_of_prev and part_of_next
    else:
        is_part = part_of_prev or part_of_next
        
        
    if is_part:
        print("Yes")
        return True
    
    print("No")
    return False

def is_first_letter(element):
    prev_el = as_text(element.previous_sibling)
    next_el = as_text(element.next_sibling)

    if prev_el and prev_el[-1].isspace() and next_el and next_el[0].isalpha():
        return True

    return False

def remove_wrapped_in_parenthesis(dom):
    print("WRAPPED IN PARENTHESIS")
    for el in select_red_spans(dom):
        print(el)

    for el in select_red_spans(dom):
        print("Testing", el, type(el))

        prev_el = el.previous_sibling
        next_el = el.next_sibling
        print("Prev \"%s\"" % prev_el, type(prev_el))
        print("Next \"%s\"" % next_el, type(next_el))

        if prev_el != None and next_el != None:
            prev_text = as_text(prev_el)
            next_text = as_text(next_el)

            if prev_text.endswith("(") and next_text.startswith(")"):
                prev_replacement = prev_text[0:-1]
                next_replacement = next_text[1:]

                prev_el.string.replace_with(prev_replacement)
                next_el.string.replace_with(next_replacement)
                el.string.replace_with("")

                print("After transformation:")

def correct_spacing(final_text, element, original_text = None):
    print("Going to correct!")

    if original_text == None:
        original_text = final_text
    else:
        print("Was \"%s\"" % original_text)
        print("Is now \"%s\"" % final_text)


    prev_el = element.previous_sibling
    next_el = element.next_sibling

    print("Prev \"%s\"" % as_text(prev_el))
    print("Next \"%s\"" % as_text(next_el))

    prev_text = as_text(prev_el)
    next_text = as_text(next_el)

    if final_text:
        #if len(final_text) > 1:
            if prev_text and prev_text[-1].isalpha() and final_text[0].isalpha() and not original_text[0].isalpha():
                final_text = " " + final_text

            if next_text and next_text[0].isalpha() and final_text[-1].isalpha() and not original_text[-1].isalpha():
                final_text += " "
    elif not is_part_of_word(element, True):
        if prev_text and prev_text[-1].isalpha() and next_text and next_text[0].isalpha():
            final_text = " "

    #print("Result after correcting: \"%s\"" % final_text)
    return final_text

def handle_struck_text(el):
    c = children_with_content(el)
    #print("There are ", len(c), " children: ", c)

    if len(c) == 1:
        if is_part_of_word(el):
            return el.get_text() # leave it as it is
        else:
            return correct_spacing(el.get_text(), el)
    else:
        for child in el.children:
            if child.name == None:
                child.extract() # remove every text node

        for struck in el.select(STRUCK_TEXT):
            #print("Struck: ", struck)
            
            struck.string = correct_spacing(struck.get_text(), struck)
            #print("Corrected to: \"%s\"" % struck.string)
        
        return correct_spacing(el.get_text(), el)

def is_surrounded_by(element, left, right):
    print("Checking if %s is surrounded by %s and %s" % (as_text(element), left, right))

    prev_el = element.previous_sibling
    next_el = element.next_sibling

    prev_text = as_text(prev_el)
    next_text = as_text(next_el)

    print("Left: \"" + prev_text + "\"")
    print("Right: \"" + next_text + "\"")


    result = (prev_text and prev_text.endswith(left) and
            next_text and next_text.startswith(right))

    print(result)

    return result

def remove_within_square_brackets(dom):
    for section in dom.select("strong"):
        final_text = section.get_text()

        if is_surrounded_by(section, '[', ']'):
            section.previous_sibling.string = section.previous_sibling.string[:-1]
            section.next_sibling.string = section.next_sibling.string[1:]
            final_text = ''

        #print("Original: \"%s\"" % section)

        final_text = ESSAY_TEXT_SUB3.sub('', final_text)
        final_text = ESSAY_TEXT_SUB2.sub('', final_text)
        #print("New: \"%s\"" % final_text)

        section.string = final_text

def handle_coloured_section(el):
    text = el.get_text()

    #print("Original text: \"%s\"" % text)

    if text.isspace():
        return text

    underscored = el.find_all("u", recursive=False, limit=1)
    if len(underscored) == 1:
        underscored_text = as_text(underscored[0])
        if len(underscored_text) > 1:
            return text

    # Handles constructions of the form:
    # <red>PUNCT</red> (<red>PUNCT</red> ...
    # Where it should be left as it is in this stage
    # and replaced with a regex after processing
    if PUNCTUATION.match(text):
        #print("!!! MATCHED:", text)
        next_el = el.next_sibling
        next_text = as_text(next_el)
        if next_text.startswith(' (') or next_text.startswith('('):
            if PUNCTUATION.match(as_text(next_el.next_sibling)):
                return text

    # Handles situations such as <red>(Vírgula) j</red>á que
    has_struck_child = el.select_one(STRUCK_TEXT) != None
    if not has_struck_child:
        #print("--> Before: \"%s\"" % text)
        new_text = PARENTHESIZED_CORRECTION.sub('', text)
        if new_text != text:
            #print("--> Changed to: \"%s\"" % new_text)
            text = new_text
            el.string = new_text
        #print("--> After: \"%s\"" % text)


    has_letter = True in (c.isalpha() for c in text)

    if has_letter and is_part_of_word(el) and not has_struck_child:
        if text == 'ç':
            return 'c'

        decoded = unidecode(text)

        if decoded != text:
            return decoded # if it had an accent, remove the accent
        elif len(text) == 1 and text.isupper():
            return text.lower() # if it got corrected to uppercase, undo it
        elif len(text) == 1 and is_first_letter(el) and not text.isupper():
            return text.upper()
        else:
            return ""
    else:
        if has_struck_child:
            return handle_struck_text(el)
    
    return ""

def handle_recent_content(dom):
    for el in dom.select(ORANGE_SPAN):
        struck_parents = list(el.find_parents("s"))
        old_text = el.get_text()

        #print("Old text: \"%s\"" % old_text)
        #print("$ It has %d parents" % len(struck_parents))
        if len(struck_parents) > 0:
            continue # this one is struck, so it's part of the original text
        
        final_text = handle_coloured_section(el)
        #print("New text: \"%s\"" % final_text)

        if el.select_one(STRUCK_TEXT) != None:
            for child in el.children:
                if child.name == None:
                    child.extract() # remove every text node
        
        if final_text != old_text:
            el.replace_with(final_text)

def handle_red_content(dom):
    for el in select_red_spans(dom):
        struck_parents = list(el.find_parents("strike")) + list(el.find_parents("s"))

        if len(struck_parents) > 0:
            continue

        #print("Looking @ element: ", el)
        original = el.get_text()
        final_text = handle_coloured_section(el)
        final_text = correct_spacing(final_text, el, original)

        el.string = final_text

    remove_wrapped_in_parenthesis(dom)

def clean_content(dom):
    for style in dom.select("body style"):
        style.decompose()

    q = None
    # if dom.select_one("div.OutlineElement") != None:
    q = dom.select("body > *")

    elements = []
    after_initial_ad = False

    for el in q:
        if el.name in ["p", "div", "span"]:
            print(el.attrs)
            if "class" in el.attrs and "publicidade-content" in el.attrs["class"]:
                after_initial_ad = not after_initial_ad
            elif after_initial_ad:
                elements.append(el)

    print("Kept")
    print(elements)

    # else:
    #     q = dom.select("body > p")
    return BeautifulSoup(''.join(map(str, elements)))

def handle_content_alternative(html, url):
    dom = BeautifulSoup(html.replace("*", ""))
    dom = clean_content(dom)

    # print("========== $$$ ==========")
    # print(dom.get_text())
    # print("== * ==")

    if dom.select_one(ORANGE_SPAN) != None:
        print("This is an orange essay.")
        handle_recent_content(dom) # It's a recent essay
    elif len(select_red_spans(dom)) > 0 and not find_old_evidence(dom):
        print("This is a red essay.")
        handle_red_content(dom)            
    else: # One of the old ones
        print("This is an old essay.")
        remove_within_square_brackets(dom)
    
    # print("========== $$$ ==========")
    # print(dom.get_text())
    # print("== * ==")
    
    
    
    print("Paragraphs before replacements:")
    paragraphs = split_in_paragraphs(dom)
    # for i, paragraph in enumerate(paragraphs):
    #     print("%d. %s" % (i + 1, paragraph))

    count = len(paragraphs)
    if count in paragraph_summary.keys():
        paragraph_summary[count].append(url)
    else:
        paragraph_summary[count] = [url]

    for k, v in paragraph_summary.items():
        print(k, " paragraphs: ", len(v))
    print("============================================================")


    final_text = "\n".join(paragraphs)
    final_text = CORRECTED_PUNCTUATION.sub(r'\1', final_text)
    final_text = final_text.replace(CORRECTED_FULL_STOP, '')
    final_text = final_text.replace(CORRECTED_COMMA, '')
    final_text = final_text.replace(CORRECTED_SEMICOLON, '')
    final_text = final_text.replace(EMPTY_PARENTHESIS, '')
    final_text = PARENTHESIZED_PUNCTUATION.sub('', final_text)
    final_text = ESSAY_TEXT_SUB3.sub('', final_text)
    final_text = ESSAY_TEXT_SUB2.sub('', final_text)

    return final_text, []

def handle_essay_comments(html):
    d = pq(html)
    if d.text() == '':
        return '', []
    comments = h.handle(d.html())
    comments = ESSAY_COMMENTS_SUB.sub('', comments)
    comments = ESSAY_COMMENTS_SUB2.sub('', comments)
    comments = remove_double_breaks(strip(comments))
    return comments

class BrasilEscolaSpider(scrapy.Spider):
    name =  'brasilescolaspider'
    allowed_domains = ['vestibular.brasilescola.uol.com.br']
    start_urls = [
        'https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/',
        #"https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-a-retomada-espaco-publico-nas-cidades.htm",
        # 'https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-caminhos-para-superar-os-desafios-encontrados-pelos-negros-atualmente.htm',
        # "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-Agua-desafio-uso-racional-preservacao.htm",
        # "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-estamos-nos-relacionando-forma-superficial.htm",
        # "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-porte-armas-pela-populacao-civil.htm",
        # "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-desinformacao-historica-um-problema-mil-consequencias.htm",
        # "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-os-caminhos-viaveis-para-uma-saude-publica-qualidade.htm",
        # "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-favelizacao.htm",
        # "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-como-combater-radicalismos-como-estado-islamico.htm",
        # "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-diversidade-sexual-um-debate-social.htm",
        # "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-feminicidio-no-brasil-um-debate-importante-sobre-violencia-contra.htm",
        # "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-equidade-genero-no-brasil-um-desafio.htm",
        # "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-mudanca-valores-conceito-familia-no-seculo-xxi.htm",
        # "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-os-refugiados-tentativa-buscar-sobrevivencia-outros-paises-imigracao.htm",
        # "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-reforma-politica-que-deve-ser-mudado.htm",
        # 'https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-informacao-sociedade-combate-as-fake-news-ano-eleicoes-presidenciais.htm',
    ]

    def parse(self, response):
        prompt_url = response.url
        print('Reading prompt from URL {0}'.format(prompt_url))
        description, info, date = handle_prompt_content(response.css('#secao_texto').extract_first())
        yield {
            'type': 'prompt',
            'title': get_text(response, '.definicao').replace('Tema: ', ''),
            'description': description,
            'info': info,
            'url': prompt_url,
            'date': date
        }
    
        for essay_url in response.css('table#redacoes_corrigidas a::attr(href)').extract():
            # if '8412' not in essay_url:# and '13591' not in essay_url:
            #    continue
            
            print(essay_url)
            print('Reading essay from URL {0}'.format(essay_url))
            yield response.follow(essay_url, self.parse_essay, meta={'prompt': prompt_url})
            # break

        next_page = response.css('div.paginador a::attr(href)').extract()[0]
        if next_page != '': # and 'caminhos' in next_page:
           yield response.follow(next_page, self.parse)

    def closed(self, reason):
        with open("paragraphs.json", "w") as paragraphs_file:
            paragraphs_file.write(json.dumps(paragraph_summary))

    def parse_essay(self, response):
        try:
            print("URL -->")
            print(response.url)
            title = strip(get_text(response, '.conteudo-pagina h1').replace('Banco de Redações', ''))
            scores = {}

            score_items = response.css('.conteudo-pagina table tr td:nth-child(2)::text').extract()[1:6]
            if extract_number(score_items[0]) == -1: 
                score_items = response.css('.conteudo-pagina table tr td:nth-child(3)::text').extract()[0:5]

            for i, score_text in enumerate(score_items):
                scores['Competência {0}'.format(i+1)] = extract_number(score_text)

            score_text = response.css('.conteudo-pagina table tr td[colspan="2"] span::text').extract_first()
            total_score = extract_number(score_text)
            if total_score == -1: total_score = response.css('.conteudo-pagina table tr td:nth-child(2)::text').extract()[6]

            html_text = ''.join(response.css('.conteudo-pagina .conteudo-materia > *').extract())
            review = remove_double_breaks(get_div_text(html_text))
            original_text, errors = handle_content_alternative(html_text, response.url)

            print("URL -->")
            print(response.url)
            print("THIS WOULD GO INTO THE JSON FILE AS \"text\"")
            print(original_text)
            print("END OF TEXT")

            html_comments = ''.join(response.css('.conteudo-pagina .conteudo-materia > div').extract())
            comments = handle_essay_comments(html_comments)
            yield {
                'type': 'essay',
                'prompt': response.meta['prompt'],
                'date': get_text(response, '#redacao_dt_tema_left').replace('Redação enviada em ', ''),
                'title': title,
                'text': original_text,
                'final_score': total_score,
                'criteria_scores': scores,
                'url': response.url,
                'review': review,
                'errors': errors,
                'comments': comments
            }
        except Exception as e:
            traceback.print_exc()
            input("Press something to continue.")


