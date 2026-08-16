from flask import Flask, request, jsonify
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

def gerar_rbxlx(part_data_list):
    roblox_xml = ET.Element("roblox", {
        "xmlns:xmime": "http://www.w3.org/2005/05/xmlmime",
        "version": "4"
    })
    
    workspace = ET.SubElement(roblox_xml, "Item", {"class": "Workspace", "referent": "RBX_WORKSPACE"})
    properties = ET.SubElement(workspace, "Properties")
    name_prop = ET.SubElement(properties, "string", {"name": "Name"})
    name_prop.text = "Workspace"

    for index, item in enumerate(part_data_list):
        part = ET.SubElement(workspace, "Item", {"class": "Part", "referent": f"RBX_PART_{index}"})
        part_props = ET.SubElement(part, "Properties")
        
        p_name = ET.SubElement(part_props, "string", {"name": "Name"})
        p_name.text = str(item.get("Name", "Part"))
        
        pos_data = item.get("Position", {})
        p_pos = ET.SubElement(part_props, "Vector3", {"name": "Position"})
        ET.SubElement(p_pos, "X").text = str(pos_data.get("X", 0))
        ET.SubElement(p_pos, "Y").text = str(pos_data.get("Y", 0))
        ET.SubElement(p_pos, "Z").text = str(pos_data.get("Z", 0))

        size_data = item.get("Size", {})
        p_size = ET.SubElement(part_props, "Vector3", {"name": "size"})
        ET.SubElement(p_size, "X").text = str(size_data.get("X", 4))
        ET.SubElement(p_size, "Y").text = str(size_data.get("Y", 1.2))
        ET.SubElement(p_size, "Z").text = str(size_data.get("Z", 2))

    return ET.tostring(roblox_xml, encoding="utf-8", method="xml")

@app.route('/publicar', methods=['POST'])
def publicar():
    try:
        dados_json = request.json
        api_key = request.headers.get('x-api-key')
        universe_id = request.headers.get('universe-id')
        place_id = request.headers.get('place-id')

        if not api_key or not universe_id or not place_id:
            return jsonify({"erro": "Headers 'x-api-key', 'universe-id' e 'place-id' sao obrigatorios."}), 400

        conteudo_rbxlx = gerar_rbxlx(dados_json)

        url_roblox = f"https://apis.roblox.com/universes/v1/{universe_id}/places/{place_id}/versions?versionType=Published"
        headers_roblox = {
            "x-api-key": api_key,
            "Content-Type": "application/octet-stream"
        }

        resposta = requests.post(url_roblox, headers=headers_roblox, data=conteudo_rbxlx)

        return jsonify({
            "status": resposta.status_code,
            "resposta_roblox": resposta.text
        })

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
