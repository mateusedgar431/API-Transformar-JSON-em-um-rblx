from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

def gerar_rbxlx_string(part_data_list):
    """
    Gera o XML .rbxlx com os cabecalhos padrao do Roblox para evitar bloqueio do WAF.
    """
    parts_xml = ""
    for index, item in enumerate(part_data_list):
        p_name = item.get("Name", "Part")
        
        pos = item.get("Position", {})
        px, py, pz = pos.get("X", 0), pos.get("Y", 0), pos.get("Z", 0)
        
        size = item.get("Size", {})
        sx, sy, sz = size.get("X", 4), size.get("Y", 1.2), size.get("Z", 2)

        parts_xml += f'''
        <Item class="Part" referent="RBX_PART_{index}">
            <Properties>
                <string name="Name">{p_name}</string>
                <Vector3 name="Position">
                    <X>{px}</X>
                    <Y>{py}</Y>
                    <Z>{pz}</Z>
                </Vector3>
                <Vector3 name="size">
                    <X>{sx}</X>
                    <Y>{sy}</Y>
                    <Z>{sz}</Z>
                </Vector3>
            </Properties>
        </Item>'''

    rbxlx_full = f'''<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">
    <External>null</External>
    <External>nil</External>
    <Item class="Workspace" referent="RBX_WORKSPACE">
        <Properties>
            <string name="Name">Workspace</string>
        </Properties>
        {parts_xml}
    </Item>
</roblox>'''

    return rbxlx_full.encode('utf-8')


@app.route('/publicar', methods=['POST'])
def publicar():
    try:
        dados_json = request.json
        api_key = request.headers.get('x-api-key')
        universe_id = request.headers.get('universe-id')
        place_id = request.headers.get('place-id')

        if not api_key or not universe_id or not place_id:
            return jsonify({"erro": "Headers 'x-api-key', 'universe-id' e 'place-id' sao obrigatorios."}), 400

        conteudo_rbxlx = gerar_rbxlx_string(dados_json)

        url_roblox = f"https://apis.roblox.com/universes/v1/{universe_id}/places/{place_id}/versions?versionType=Published"
        
        headers_roblox = {
            "x-api-key": api_key,
            "Content-Type": "application/xml",
            "User-Agent": "RobloxOpenCloudClient/1.0"
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
