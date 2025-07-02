import requests
import boto3
import uuid
from bs4 import BeautifulSoup
import os
import json

def lambda_handler(event, context):
    api_key = os.environ['SCRAPINGBEE_API_KEY']
    url = "https://ultimosismo.igp.gob.pe/ultimo-sismo/sismos-reportados"

    response = requests.get(
        "https://app.scrapingbee.com/api/v1/",
        params={
            'api_key': api_key,
            'url': url,
            'render_js': "true",
            'wait': "5000"
        }
    )

    if response.status_code != 200:
        return {
            'statusCode': response.status_code,
            'body': json.dumps({'error': 'Error al acceder a la página usando ScrapingBee'})
        }

    soup = BeautifulSoup(response.content, 'html.parser')
    table_html = soup.find('table')
    if not table_html:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'No se encontró la tabla de sismos'})
        }

    # Obtener cabecera dinámica
    headers = []
    thead = table_html.find('thead')
    if thead:
        headers = [th.text.strip() for th in thead.find_all('th')]
    else:
        # En caso no exista thead, usar los primeros <tr><th> como cabecera
        first_row = table_html.find('tr')
        if first_row:
            headers = [cell.text.strip() for cell in first_row.find_all(['th', 'td'])]

    if not headers:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'No se pudieron extraer los encabezados de la tabla'})
        }

    # Procesar filas
    rows = []
    for tr in table_html.find_all('tr')[1:]:
        tds = tr.find_all('td')
        if len(tds) < len(headers) - 1:  # margen de error
            continue
        row = {
            "id": str(uuid.uuid4())
        }
        for i, header in enumerate(headers[:-1]):  # última columna es enlace (lo asumimos como texto)
            row[header] = tds[i].text.strip()
        row[headers[-1]] = "Ver reporte sísmico"
        rows.append(row)

    # Guardar en DynamoDB
    dynamodb = boto3.resource('dynamodb')
    dynamodb_table = dynamodb.Table('TablaSismosIGP')

    # Eliminar registros previos
    scan = dynamodb_table.scan()
    with dynamodb_table.batch_writer() as batch:
        for item in scan['Items']:
            batch.delete_item(Key={'id': item['id']})

    # Insertar nuevos registros
    for item in rows:
        dynamodb_table.put_item(Item=item)

    # Retornar los datos scrapeados en el response
    return {
    'statusCode': 200,
    'body': {
        'mensaje': f'{len(rows)} registros insertados correctamente',
        'registros': rows
    },
    'headers': {
        'Content-Type': 'application/json'
    }
    }

