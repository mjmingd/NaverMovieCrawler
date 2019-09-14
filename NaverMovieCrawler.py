#!/usr/bin/env python
# -*- coding: utf-8, euc-kr -*-

from selenium import webdriver
from selenium.common.exceptions import *
from bs4 import BeautifulSoup
from urllib import request
import re
import json
from collections import OrderedDict
import platform
import argparse
import csv



class NaverMovieCrawler() :
    def __init__(self) :
        self.agrs = ['load', 'save', 'maxpages']
        self.user_operating_system = str(platform.system())
        print('user_operating_system: ', self.user_operating_system)
        self.wd_path = './webdriver/' + self.user_operating_system + '/chromedriver'
        self.webdriver = webdriver.Chrome(self.wd_path)
        self.defaultURL = "https://movie.naver.com/"
        self.movieCommentData = OrderedDict()
        self.errorList = list()
        self.maxpages = args.maxpages





    def load_movieList(self, fileName):
        # 크롤러에 들어갈 수 있도록 movieList 생성하기
        # movieList = [(영화제목, 제작년도),(영화제목, 제작년도),...]
        with open("./data/"+fileName) as f:
            file = json.load(f)
            data = file["movieListResult"]["movieList"]
            numMovie = len(data)
            movieList = []
            for movie in data:
                if movie["movieNm"] != '':
                    movieList.append((movie["movieNm"], movie["prdtYear"]))  # (영화제목, 제작년도)
                else:
                    movieList.append((movie["movieNmEn"], movie["prdtYear"]))
            print("Prepared movie List")

        return movieList

    def save_data(self, fileName):
        with open("./data/" + fileName + ".json", 'w', encoding="utf-8") as f:
            json.dump(self.movieCommentData, f, ensure_ascii=False, indent='\t')

        with open("./data/Nodata.csv", 'w', newline='') as ef :
            csvWriter = csv.writer(ef)
            for error in self.errorList :
                csvWriter.writerow(error)

        print("Successfully Saved")



    def get_movie(self, movieData):
        # title을 검색하여 제작연도를 비교하여 영화를 찾기
        # input : movieData(영화제목, 제작년도)
        # output : 해당 영화페이지로 이동
        title, pYear = movieData

        self.webdriver.get(self.defaultURL)
        elem = self.webdriver.find_element_by_xpath('//*[@id="ipt_tx_srch"]')
        elem.send_keys(title)
        # 영화 검색
        self.webdriver.find_element_by_xpath('//*[@id="jSearchArea"]/div/button').click()
        # 기다리는 시간 설정
        self.webdriver.implicitly_wait(5)
        # 영화 검색 탭으로 이동
        self.webdriver.find_element_by_xpath('//*[@class="search_menu"]/li[2]/a').click()


        try :
            # 영화 검색이 1페이지 이상 나올 경우?!?!? 1페이지에 10개
            srch_res = self.webdriver.find_element_by_xpath('//*[@id="old_content"]/div[1]/span[@class="num"]').text
            s_idx, e_idx = srch_res.find('/'), srch_res.find('건')
            num_movies = int(srch_res[s_idx+2: e_idx])

            candidates = self.webdriver.find_elements_by_xpath('//*[@class="search_list_1"]/li')

            for i in range(1,len(candidates)+1) :
                candi_title = self.webdriver.find_element_by_xpath(
                    '//*[@class="search_list_1"]/li[{}]/dl/dt/a'.format(str(i))).text
                candi_year = self.webdriver.find_element_by_xpath(
                    '//*[@class="search_list_1"]/li[{}]/dl/dd[2]/a[contains (@href, "year")]'.format(str(i))).text

                if title in candi_title and pYear == candi_year :
                    self.webdriver.find_element_by_xpath(
                        '//*[@class="search_list_1"]/li[{}]/dl/dt/a/strong'.format(str(i))).click()
                    print("Matched")

                    codeUrl = self.webdriver.find_element_by_xpath('/html/head/meta[@property="og:url"]')\
                        .get_attribute("content")
                    code = codeUrl[codeUrl.find('=')+1 : ]
                    matched = OrderedDict()
                    matched["movieNm"] = title
                    matched["prdtYear"] = pYear
                    matched["synopsis"] = self.get_synopsis()
                    matched["reporters"] = self.get_reporter()
                    matched["comments"] = self.get_comments()

                    return (code, matched)



                else :
                    if i == len(candidates)+1 :
                        self.errorList.append(movieData)
                        print("No data")
                        return None
                    else :
                        print("not Matched")

        except NoSuchElementException :
            print("No data")
            self.errorList.append(movieData)
            return None



    def get_synopsis(self):
        # 해당 영화페이지에서 시놉시스를 받아옴
        # output : synopsis(str)
        synop = self.webdriver.find_element_by_xpath('//*[@class="story_area"]/p[@class="con_tx"]').text
        return synop

    def get_reporter(self):
        # 전문가 평점 크롤링

        reportersComments = []
        self.webdriver.find_element_by_xpath('//*[@id="movieEndTabMenu"]/li/a[contains (@href, "point")]').click()
        if self.webdriver.find_elements_by_xpath('//*[@class="score_result"]/ul/li') :
            reporters = self.webdriver.find_elements_by_xpath('//*[@class="score_result"]/ul/li')

            for reporter in reporters :

                score, text, magazine, name = reporter.text.split('\n')
                comment = OrderedDict()
                comment["text"] = text
                comment["score"] = score
                comment["name"] = magazine + name

                reportersComments.append(comment)
        return reportersComments

    def get_comments(self):
        # 평가 페이지(140자 평가)에서 개봉후 네티즌 평점을 받아옴
        # commentsList = [comment1, comment2, ... ]

        # comment page로 이동
        self.webdriver.find_element_by_xpath('//*[@id="movieEndTabMenu"]/li/a[contains (@href, "point")]').click()
        self.webdriver.switch_to.frame('pointAfterListIframe')
        numComments = self.webdriver.find_element_by_xpath('//*[@class="total"]/em').text # 전체 comment갯수
        numComments = int(numComments.replace(',',''))
        if numComments == 0 :
            return []
        elif numComments <= 10 :
            numCommentPages = 1
        else :
            numCommentPages = numComments//10 + 1

        numCommentPages = min(numCommentPages, self.maxpages)
        pageUrlDefault = self.webdriver.find_element_by_xpath(
            '//*[@class="paging"]/div/a').get_attribute("href")[:-1]
        commentsList = []


        for i in range(1, numCommentPages):
            pageUrl = pageUrlDefault + str(i)
            page = request.urlopen(pageUrl)
            html = page.read().decode('utf-8')
            bs = BeautifulSoup(html, 'html.parser')
            result = bs.select(".score_result li")

            if not len(result) : break
            for li in result :

                comment = OrderedDict()
                comment["text"] = li.select('.score_reple p')[0].text
                comment["score"] = li.select('.star_score em')[0].text
                comment["like"] = li.select('.btn_area strong span')[0].text
                comment["notLike"] = li.select('.btn_area strong span')[1].text

                commentsList.append(comment)

        print("got commentsList")
        return commentsList




if __name__ == "__main__" :
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--load',
                        help='filename for loading', type=str, default='testList')
    parser.add_argument('-s', '--save',
                        help='filename for saving', type=str, default='movies')
    parser.add_argument('-mp', '--maxpages',
                        help='set maximum pages of comments', type=int, default=10)  # comments = pages * 10

    args = parser.parse_args()



    NMC = NaverMovieCrawler()
    movieList = NMC.load_movieList(args.load)

    for movieData in movieList:
        result = NMC.get_movie(movieData)
        if result != None :
            code, data = result
            NMC.movieCommentData[code] = data

    NMC.save_data(args.save)
