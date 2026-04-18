@echo off
REM BFScan SOAP 请求测试脚本

curl -X POST http://127.0.0.1:8283 ^
  -H "Content-Type: text/xml; charset=utf-8" ^
  -H "SOAPAction: \"B_FScan\"" ^
  -d "<?xml version=\"1.0\" encoding=\"UTF-8\"?><soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:srrc=\"http://www.srrc.org.cn\"><soapenv:Body><srrc:requestbody><srrc:appid>123456</srrc:appid><srrc:userid>RX_admin</srrc:userid><srrc:mfid>53090001140012</srrc:mfid><srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid><srrc:equpara><srrc:groupitems><srrc:groupitem><srrc:groupid>1</srrc:groupid><srrc:items><srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137MHz</srrc:paravalue></srrc:item><srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173MHz</srrc:paravalue></srrc:item><srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25kHz</srrc:paravalue></srrc:item><srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item><srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item></srrc:items></srrc:groupitem></srrc:groupitems></srrc:equpara><srrc:outputchannel><srrc:mode>source</srrc:mode><srrc:datachannel>stream</srrc:datachannel></srrc:outputchannel></srrc:requestbody></soapenv:Body></soapenv:Envelope>"
