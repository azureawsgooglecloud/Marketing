from flask import Flask, render_template, request, jsonify,session
import pypyodbc as pyodbc
import sys
import time
import datetime
import os
from flask import render_template
import json
import pandas as pd

connection_string = "Driver={ODBC Driver 13 for SQL Server};Server=tcp:daub.database.windows.net,1433;Database=DAUB_BI;Uid=AzureDataFactory;Pwd={X17j8T@$1Bj5};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
app = Flask(__name__)

# In order to use session in flask you need to set the secret key in your application settings. 
# Secret key is a random key used to encrypt your cookies and save send them to the browser.
app.secret_key = 'RxeTECU4y6AaEWgL57JwtCC9'

uploadFolder = '/static/uploads'
dir_path = os.path.dirname(os.path.realpath(__file__))



@app.route('/', methods=['GET', 'POST'])
def home():
	if request.method == 'POST':
		# print(request)
		data = request.form
		print(data)
		resp_dict = {}
		filename = ''

		if len(session['filename']) > 0:
			filename = session['filename']
		
		try:
			query_string = """INSERT INTO Optimove.CampaignTracker ( CAMPAIGNNAME, CAMPAIGNDETAILS, CAMPAIGNSTARTDATE, CAMPAIGNENDDATE, CAMPAIGN_ID, CAMPAIGNBRANDNAME, CAMPAIGNCHANNEL, CAMPAGINTYPE, CAMPAGINFILENAME, Original_filename) VALUES('{}','{}','{}','{}','{}', '{}','{}','{}','{}','{}')""".format(data['campaign_name'],data['campaign_details'],data['campaign_start'],data['campaign_end'],data['campaign_uniqueId'], data['campaign_type'], data['campaign_brand_name'], data['campaign_channel_type'], filename, data['original_filename'] )
			print(query_string)
		except Exception as e:
			resp_dict = { 'error': 'Wrong params', 'statusCode': '400' }
			return jsonify(resp_dict)
		# Logic to store the data in the database
		try:			
			db = pyodbc.connect(connection_string)
			db.cursor().execute(query_string)
			db.commit()
												
			if data['got_file'] == 'true' and len(session['filename']) > 0:
				cursor = db.cursor()
				cursor.execute('SELECT @@IDENTITY')
				row = cursor.fetchone()			
				if row:					
					resp_dict = saveCsvToSQL(db,row[0], data['campaign_uniqueId'])															
				else:
					resp_dict = { 'error': 'Failed to save Campaign info to DB - 00', 'statusCode': '400'}
			else:
				resp_dict = { 'success': 'true', 'statusCode': '200', 'uniqueId': data['campaign_uniqueId']}			

			db.close()							
		except Exception as e:
			resp_dict = { 'error': str(e), 'statusCode': '400' }

		return jsonify(resp_dict)


	elif request.method == 'GET':
		# return render_template('index.html')
		return app.send_static_file('index.html')

@app.route('/process',  methods=['GET', 'POST'])
def process_page():
    if request.method == 'POST':
        # Get the name of the uploaded file
        file = request.files['fileToupload']
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        input_file = UPLOAD_FOLDER + filename
        #print input_file
			
# Used for AJAX and ignore in current app implementation. This is for Phase 2 		
@app.route('/data', methods=['GET'])
def searchData():
	try:
		query_string = "SELECT * FROM Optimove.CampaignTracker"
		db = pyodbc.connect(connection_string)
		cursor = db.cursor()
		cursor.execute(query_string)
		query_results = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
		resp_dict = { 'success': 'true', 'statusCode': '200', 'data': query_results}
		db.close()			
		return jsonify(query_results)
	except Exception as e:
		resp_dict = { 'error': str(e), 'statusCode': '400' }
		return jsonify(resp_dict)

@app.route('/fileupload', methods=['POST'])
def file_upload():	
	filename = ''
	try:		
		file = request.files.get('file') 		
		if file:			
			filename = '{}'.format(datetime.datetime.now())	  # Original filename is replaced with datetime tokens to avoid duplicates  		
			filename = filename.replace(":", ".")			  # Replace : with .   
			file.save(os.path.join(dir_path + uploadFolder, filename))
			session['filename'] = filename
	except Exception as e:
# 		resp_dict = { 'error': 'Failed to upload file', 'statusCode': '400'}
		resp_dict = { 'error': e, 'statusCode': '400'}
		return jsonify(resp_dict)

	resp_dict = { 'success': 'true', 'statusCode': '200', 'data': filename}
	return jsonify(resp_dict)       

# Tested and Working  : 06-04
def saveCsvToSQL(db, id, uniqueId):			
	try:				
		file_location = file_location = os.path.join(dir_path + uploadFolder, session['filename'])
		print file_location
		
		if len(file_location) > 0:
			df = pd.read_csv(file_location, usecols=[0])
			listObj = list(df.itertuples(index=False, name=None))

			if len(listObj) > 0:
				return saveDataFrameToDB(db,listObj, id, uniqueId)
				
	except Exception as e:
		return { 'error': 'Failed to save data to DB - 01', 'statusCode': '400'}		

	return { 'error': 'Failed to save data to DB - 02', 'statusCode': '400'}			

# Tested and Working  : 06-04. Insert PlayerID into DB table 
def saveDataFrameToDB(db,listObj, id, uniqueId):		
	try:
		if id > 0:
			sql_statement = 'INSERT INTO Optimove.campaignTrackerPlayerDetails (campaign_id, PlayerID) VALUES ({},?)'.format(id)			
			cursor = db.cursor()
			cursor.fast_executemany = True
			cursor.executemany(sql_statement, listObj)
			db.commit()
			
			if len(listObj) != getInsertedDetailsRowCount(db,id):			
				return { 'error': 'Failed to save all data rows to DB - 03', 'statusCode': '400' , 'listObj':len(listObj) , 'count': getInsertedDetailsRowCount(db,id)}						
			
	except Exception as e:
		return { 'error': 'Failed to save data to DB - 04', 'statusCode': '400'}		

	return { 'success': 'true', 'statusCode': '200', 'uniqueId': uniqueId, 'rowInserted':len(listObj) }	


def getInsertedDetailsRowCount(db, id):	
	try:
		sql_statement = 'SELECT Count(campaign_id) FROM Optimove.campaignTrackerPlayerDetails WHERE campaign_id = {}'.format(id)
		cursor = db.cursor()
		cursor.execute(sql_statement)	
		row = cursor.fetchone()			
		if row:					
			return int(row[0])
	except Exception as e:
		return 0	

	return 0


if __name__ == '__main__':
	app.run(debug=True)