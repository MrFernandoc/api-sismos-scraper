import requests
import boto3
import uuid
from bs4 import BeautifulSoup
import os

def lambda_handler(event, context):
    # ScrapingBee API Key desde variable de entorno
    api_key = os.environ['SCRAPINGBEE_API_KEY']
    url = "https://ultimosismo.igp.gob.pe/ultimo-sismo/sismos-reportados"

    # Usar ScrapingBee para obtener el HTML renderizado
    response = requests.get(
        "https://app.scrapingbee.com/api/v1/",
        params={
            'api_key': api_key,
            'url': url,
            'render_js': "true"
        }
    )

    if response.status_code != 200:
        return {
            'statusCode': response.status_code,
            'body': 'Error al acceder a la página usando ScrapingBee'
        }

    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table')
    if not table:
        return {
            'statusCode': 404,
            'body': 'No se encontró la tabla de sismos'
        }

    headers = ["Reporte Sísmico", "Referencia", "Fecha y hora (Local)", "Magnitud", "Descargas"]

    # Procesar filas
    rows = []
    for tr in table.find_all('tr')[1:]:  # Ignorar cabecera
        tds = tr.find_all('td')
        if len(tds) < 4:
            continue
        row = {
            "id": str(uuid.uuid4()),
            headers[0]: tds[0].text.strip(),
            headers[1]: tds[1].text.strip(),
            headers[2]: tds[2].text.strip(),
            headers[3]: tds[3].text.strip(),
            headers[4]: "Ver reporte sísmico"
        }
        rows.append(row)

    # Guardar en DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('TablaSismosIGP')

    # Eliminar datos anteriores
    scan = table.scan()
    with table.batch_writer() as batch:
        for item in scan['Items']:
            batch.delete_item(Key={'id': item['id']})

    # Insertar nuevos
    for item in rows:
        table.put_item(Item=item)

    return {
        'statusCode': 200,
        'body': f"{len(rows)} registros insertados correctamente"
    }
