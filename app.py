from flask import Flask, make_response, jsonify, request, current_app, send_file
import mysql.connector
from flask_cors import CORS
from fpdf import FPDF

app = Flask(__name__)
CORS(app)

db_config = {
    'host': '10.30.10,13',
    'user': 'bestshop',
    'password': 'bestshop',
    'database': 'school_question',
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

def get_scenario_id(cursor, subject_id, title, scenario):
    cursor.execute("""
        SELECT scenario_id
        FROM scenarios
        WHERE subject_id = %s AND scenario_title = %s AND scenario = %s
    """, (subject_id, title, scenario))
    result = cursor.fetchone()
    return result['scenario_id'] if result else None

@app.route('/api/school/generate_pdf', methods=['GET'])
def generate_pdf():
    try:
        subject_id = int(request.args.get('subject_id'))

        with get_db_connection() as connection, connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM subjects WHERE subject_id = %s", (subject_id,))
            subject = cursor.fetchone()
            if not subject:
                return jsonify({'error': 'Subject not found'}), 404

            cursor.execute("SELECT * FROM scenarios WHERE subject_id = %s", (subject_id,))
            scenarios = cursor.fetchall()

            pdf = FPDF('P', 'mm', 'A4')
            file_name = f"{subject_id}_{subject['subject'].replace(' ', '_')}_questions.pdf"

            pdf.add_page()
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(0, 10, 'Questions', 0, 1, 'C')
            pdf.ln(5)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, f'Subject: {subject["subject"]}', 0, 1)
            pdf.cell(0, 10, f'Subject Type: {subject["subject_type"]}', 0, 1)
            pdf.ln(5)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            
            question_number = 1
            for scenario in scenarios:
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, f'Scenario Title: {scenario["scenario_title"]}', 0, 1)
                pdf.multi_cell(0, 10, 'Scenario:', 0, 'L')
                pdf.set_font('Arial', '', 12)
                pdf.multi_cell(0, 10, f'{scenario["scenario"]}', 0, 'L')

                cursor.execute("SELECT * FROM questions WHERE scenario_id = %s", (scenario["scenario_id"],))
                questions = cursor.fetchall()
                for question in questions:
                    pdf.set_font('Arial', '', 12)
                    pdf.cell(0, 10, f'{question_number}.{question["question"]}', 0, 1) 
                    pdf.set_font('Arial', 'B', 12)
                    pdf.cell(0, 10, f'Options:', 0, 1)
                    pdf.set_font('Arial', '', 12)
                    pdf.cell(0, 10, f'  1) {question["option_1"]}', 0, 1)
                    pdf.cell(0, 10, f'  2) {question["option_2"]}', 0, 1)
                    pdf.cell(0, 10, f'  3) {question["option_3"]}', 0, 1)
                    pdf.cell(0, 10, f'  4) {question["option_4"]}', 0, 1)
                    option_answer = question["answer"]
                    pdf.set_font('Arial', 'B', 12)
                    answer_text = f'Answer: {question["answer"]}) {question["option_" + str(option_answer)]}'
                    pdf.cell(0, 10, answer_text, 0, 1)
                    question_number += 1

                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(1)

            pdf_output_path = file_name
            pdf.output(pdf_output_path)

            response = make_response(send_file(pdf_output_path, as_attachment=True))
            response.headers["Content-Disposition"] = f"attachment; filename={file_name}"

            pdf_link = f"http://192.168.43.174:5000/{pdf_output_path}"
            return jsonify({'response': response, 'pdf_link': pdf_link})
    except ValueError:
        return jsonify({'error': 'Invalid subject ID'}), 400
    except mysql.connector.Error as e:
        current_app.logger.error(f"MySQL Error: {str(e)} | Subject ID: {subject_id}")
        return jsonify({'error': f'Internal Server Error: {str(e)}'}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected Error: {str(e)} | Subject ID: {subject_id}")
        return jsonify({'error': f'Internal Server Error: {str(e)}'}), 500

@app.route('/api/school/addQuestions', methods=['POST'])
def add_question():
    try:
        data = request.form  
        subject_id = data['subject_id']
        title = data['title']
        scenario = data['scenario']
        question = data['question']
        option_1 = data['option_1']
        option_2 = data['option_2']
        option_3 = data['option_3']
        option_4 = data['option_4']
        answer = data['answer']

        with get_db_connection() as connection, connection.cursor(dictionary=True) as cursor:
            scenario_id = get_scenario_id(cursor, subject_id, title, scenario)
            if scenario_id is None:
                cursor.execute("""
                    INSERT INTO scenarios
                    (subject_id, scenario_title, scenario) 
                    VALUES (%s, %s, %s)
                """, (subject_id, title, scenario))
                scenario_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO questions 
                (scenario_id, question, option_1, option_2, option_3, option_4, answer) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (scenario_id, question, option_1, option_2, option_3, option_4, answer))

            connection.commit()
            return jsonify({'success': True, 'scenario_id': scenario_id}), 200

    except mysql.connector.Error as e:
        app.logger.error(f"MySQL Error: {str(e)} | Request Data: {data}")
        return jsonify({'error': f'Internal Server Error: {str(e)}'}), 500
    except Exception as e:
        app.logger.error(f"Unexpected Error: {str(e)} | Request Data: {data}")
        return jsonify({'error': f'Internal Server Error: {str(e)}'}), 500

@app.route('/api/school/dropdown/<path:text>', methods=['GET'])
def get_dropdown_options(text):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        if text == 'subjects':
            cursor.execute('SELECT subject FROM subjects GROUP BY subject')
            options = [result['subject'] for result in cursor.fetchall()]
        elif text.startswith('subjects/'):
            subject = text.split('/')[1]
            cursor.execute('SELECT subject_id, subject_type FROM subjects WHERE subject = %s', (subject,))
            options = [{'subject_id': result['subject_id'], 'subject_type': result['subject_type']} for result in cursor.fetchall()]
        else:
            return jsonify({'error': 'Invalid path parameter'})
        return jsonify(options)
    except Exception as e:
        app.logger.error(f"Unexpected Error: {str(e)}")
        return jsonify({'error': str(e)})
    finally:
        cursor.close()
        connection.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
