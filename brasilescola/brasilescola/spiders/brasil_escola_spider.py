"""This spider extracts essays from Brasil Escola (http://vestibular.brasilescola.uol.com.br/banco-de-redacoes/).
"""
import scrapy
import html2text
import re
import traceback
from unidecode import unidecode
from pyquery import PyQuery as pq
from bs4 import BeautifulSoup

h = html2text.HTML2Text()
h.ignore_links = True
h.ignore_images = True
h.ignore_emphasis = True
h.body_width = False

IGNORE_CHAR = re.compile(r'(^[\r\n\t\s]+|[\r\n\t\s]+$)')
EXTRACT_NUMBER = re.compile(r'[^\d](\d+([.,]\d+)?).*')
PROMPT_DESCRIPTION_SUB = re.compile(r'Saiba como fazer uma boa.+', re.DOTALL)
PROMPT_INFO_SUB = re.compile(r'.+Elabore sua redação[^\r\n]+[\r\n]*', re.DOTALL)
ESSAY_COMMENTS_SUB = re.compile(r'.+Comentários do corretor', re.DOTALL)
ESSAY_COMMENTS_SUB2 = re.compile(r'Competências avaliadas.+', re.DOTALL)
ESSAY_TEXT_SUB = re.compile(r' \[[^\]]+\] ')
ESSAY_TEXT_SUB2 = re.compile(r'\[[^\]]+\]')
ESSAY_TEXT_SUB3 = re.compile(r' \[[^\]]*\]')
RED_SPAN = 'span[style*="#FF0000"], span[style*="rgb(255"]'
STRUCK_TEXT = 'strike, s'
CORRECTED_FULL_STOP = ' (.)'
CORRECTED_COMMA = ' (,)'
CORRECTED_SEMICOLON = ' (;)'

# Handles both tags and navigable strings.
def as_text(element):
    return element.string

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

def is_part_of_word(element):
    print("Testing if part of word ", element)
    text = element.get_text()
    prev_el = element.previous_sibling
    next_el = element.next_sibling
    print("Prev \"%s\"" % prev_el)
    print("Next \"%s\"" % next_el)
    if ((prev_el and prev_el[-1].isalpha() and text[0].isalpha()) or
        (next_el and next_el[0].isalpha() and text[-1].isalpha())):
        print("Yes")
        return True
    
    print("No")
    return False

def remove_wrapped_in_parenthesis(dom):
    for el in dom.select(RED_SPAN):
        print("Testing", el, type(el))

        prev_el = el.previous_sibling
        next_el = el.next_sibling
        print("Prev \"%s\"" % prev_el, type(prev_el))
        print("Next \"%s\"" % next_el, type(next_el))

        if prev_el != None and next_el != None:
            if prev_el.endswith("(") and next_el.startswith(")"):
                prev_el.replace_with(prev_el[0:-1])
                next_el.replace_with(next_el[1:])
                el.decompose()
                print("Should remove this one")

def correct_spacing(new_text, element):
    prev_el = element.previous_sibling
    next_el = element.next_sibling

    print("Going to correct!")
    print("Prev \"%s\"" % prev_el)
    print("Next \"%s\"" % next_el)

    if prev_el and as_text(prev_el)[-1].isalpha() and new_text[0].isalpha():
        new_text = " " + new_text

    if next_el and as_text(next_el)[0].isalpha() and new_text[-1].isalpha():
        new_text += " "

    print("Result after correcting: \"%s\"" % new_text)
    return new_text

def handle_struck_text(el):
    c = children_with_content(el)
    print("There are ", len(c), " children: ", c)

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
            print("Struck: ", struck)
            
            struck.string = correct_spacing(struck.get_text(), struck)
            print("Corrected to: \"%s\"" % struck.string)
        
        return correct_spacing(el.get_text(), el)


def remove_within_square_brackets(dom):
    for section in dom.select("strong"):
        print("Original: \"%s\"" % section)

        new_text = ESSAY_TEXT_SUB3.sub('', section.get_text())
        new_text = ESSAY_TEXT_SUB2.sub('', new_text)
        print("New: \"%s\"" % new_text)

        section.replace_with(new_text)


def handle_recent_content(dom):
    for el in dom.select('span[style*="#e74c3c"]'):
        print("!!! Looking @ ", el)
        struck_parents = list(el.find_parents("s"))
        print("!!! Struck parents:")
        print(struck_parents)


def handle_content_alternative(html):
    dom = BeautifulSoup(html.replace("*", ""))
    print(dom)
    print("== # ==")
    print(dom.prettify())

    handle_recent_content(dom)
    print("========== $$$ ==========")
    remove_within_square_brackets(dom)
    print("========== &&& ==========")
    
    had_red = False
    for el in dom.select(RED_SPAN):
        print("Looking @ element: ", el)
        text = el.get_text()
        new_text = text
        print("Original text: \"%s\"" % text)
        has_letter = True in (c.isalpha() for c in text)

        if has_letter and is_part_of_word(el) and el.select_one(STRUCK_TEXT) == None:
            decoded = unidecode(text)

            if decoded != text:
                new_text = decoded # if it had an accent, remove the accent
            elif len(text) == 1 and text.isupper():
                new_text = text.lower() # if it got corrected to uppercase, undo it
            else:
                new_text = "" # otherwise remove the text itself
        else:
            if el.select_one(STRUCK_TEXT) != None:
                new_text = handle_struck_text(el)

        new_text = new_text.replace(CORRECTED_FULL_STOP, '')
        new_text = new_text.replace(CORRECTED_COMMA, '')
        new_text = new_text.replace(CORRECTED_SEMICOLON, '')
        el.replace_with(new_text)

        had_red = True


    if had_red:
        remove_wrapped_in_parenthesis(dom)

    print(dom.prettify())
    print("== * ==")
    
    
    paragraphs = list(map(lambda x: x.get_text(), dom.select("p")))
    for i, paragraph in enumerate(paragraphs):
        print("%d. %s" % (i + 1, paragraph))


    print("============================================================")

def handle_essay_content(html):
    handle_content_alternative(html)

    # TODO Fix error 'ID redacoes_corrigidas already defined' in lxml.etree.XMLSyntaxError: line 111
    d = pq(html)
    if d.text() == '':
        return '', []
    print(d.text())
    
    errors = []

    # This catches only few errors in the most recent version of the page layout
    #errors = d.find('s').map(lambda i, e: (pq(e).text())) 
    # Some of the evaluators corrections are inside a span, and the span contains the text with the fixed version
    for strike in d.find('p > span > s, p > span > strike'):
        new_text = pq(strike).text()
        print("Strike --> ", strike)
        print("New text ==> ", new_text)
        if new_text is None: continue
        # Sometimes the fixed text has spaces and the original version (selected part) has not,
        # causing words to get mixed
        review_text = pq(pq(strike).html()).remove('s, strik').text()
        print("Review text ~~> ", review_text)
        if not new_text.startswith(' ') and review_text.startswith(' '):
            new_text = ' ' + new_text
        if not new_text.endswith(' ') and review_text.endswith(' '):
            new_text = new_text + ' '
        parent = pq(strike).parent('span')       
        if parent is None: continue
        # TODO doesn't work when a span contains more than one strike
        try:
            parent.replaceWith(new_text)
        except:
            print("Could\'t replace text with {0}".format(new_text))
            
    # Remove evaluators comments from the text using span to red color it
    # TODO The span is replaced by a unwanted space when it is not between spaces, eg "est<span>r</span>eitam"
    original = h.handle(d.remove('p > span').html())
    original = strip(original.replace('~~', ''))
    original = remove_double_breaks(original)
    # Remove comments with the template "original word [fixed word]"
    original = ESSAY_TEXT_SUB.sub(' ', original)
    original = ESSAY_TEXT_SUB2.sub('', original)
    
    return original, errors

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
        #'https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-corrupcao.htm',
        #'https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-caminhos-para-superar-os-desafios-encontrados-pelos-negros-atualmente.htm',
        #"https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-Agua-desafio-uso-racional-preservacao.htm",
        #"https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-estamos-nos-relacionando-forma-superficial.htm",
        #"https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-porte-armas-pela-populacao-civil.htm",
        "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-desinformacao-historica-um-problema-mil-consequencias.htm",
        "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-os-caminhos-viaveis-para-uma-saude-publica-qualidade.htm",
        "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-favelizacao.htm",
        "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-como-combater-radicalismos-como-estado-islamico.htm",
        "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-diversidade-sexual-um-debate-social.htm",
        "https://vestibular.brasilescola.uol.com.br/banco-de-redacoes/tema-feminicidio-no-brasil-um-debate-importante-sobre-violencia-contra.htm",
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
            print(essay_url)
            if '13512' not in essay_url:# and '13591' not in essay_url:
                continue
            
            print('Reading essay from URL {0}'.format(essay_url))
            yield response.follow(essay_url, self.parse_essay, meta={'prompt': prompt_url})
            # break

        #next_page = response.css('div.paginador a::attr(href)').extract()[0]
        #if next_page != '': # and 'caminhos' in next_page:
        #    yield response.follow(next_page, self.parse)

    def parse_essay(self, response):
        try:
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

            html_text = ''.join(response.css('.conteudo-pagina .conteudo-materia > p').extract())
            review = remove_double_breaks(get_div_text(html_text))
            original_text, errors = handle_essay_content(html_text)

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


