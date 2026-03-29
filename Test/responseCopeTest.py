import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Src.responseCope import cope_send_otp_request

#处理相响应回来的路径信息，去除无关信息
cope_send_otp_request()