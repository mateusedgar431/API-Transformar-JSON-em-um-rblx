from flask import Flask, request, jsonify
import requests
import xml.sax.saxutils as saxutils

app = Flask(__name__)

def extrair_vetor(vetor_data, default_x=0, default_y=0, default_z=0):
    if isinstance(vetor_data, dict):
        return (
            vetor_data.get("X", default_x),
            vetor_data.get("Y", default_y),
            vetor_data.get("Z", default_z)
        )
    return default_x, default_y, default_z

def processar_objetos_xml(lista_objetos):
    xml_output = ""
    for idx, obj in enumerate(lista_objetos):
        props = obj.get("Properties", {})
        children = obj.get("Children", [])
        script_code = obj.get("Script")
        
        class_name = props.get("ClassName", "Part")
        obj_name = props.get("Name", f"Object_{idx}")
        
        if script_code and class_name not in ["Script", "LocalScript", "ModuleScript"]:
            class_name = "Script"

        xml_output += f'\n<Item class="{class_name}" referent="RBX_OBJ_{idx}_{abs(hash(obj_name))}">'
        xml_output += '\n  <Properties>'
        xml_output += f'\n    <string name="Name">{saxutils.escape(str(obj_name))}</string>'
        
        if "Position" in props:
            px, py, pz = extrair_vetor(props["Position"], 0, 10, 0)
            xml_output += f'''
            <Vector3 name="Position">
                <X>{px}</X><Y>{py}</Y><Z>{pz}</Z>
            </Vector3>'''
            
        if "Size" in props or "size" in props:
            sx, sy, sz = extrair_vetor(props.get("Size") or props.get("size"), 4, 1.2, 2)
            xml_output += f'''
            <Vector3 name="size">
                <X>{sx}</X><Y>{sy}</Y><Z>{sz}</Z>
            </Vector3>'''

        xml_output += '\n    <bool name="Anchored">true</bool>'
        xml_output += '\n    <bool name="CanCollide">true</bool>'

        if script_code:
            codigo_escapado = saxutils.escape(str(script_code))
            xml_output += f'\n    <ProtectedString name="Source">{codigo_escapado}</ProtectedString>'

        xml_output += '\n  </Properties>'
        
        if children:
            xml_output += processar_objetos_xml(children)
            
        xml_output += '\n</Item>'

    return xml_output

def construir_rbxlx_completo(part_data_dict):
    workspace_content = ""
    outros_servicos = ""

    if isinstance(part_data_dict, dict):
        for servico_nome, servico_dados in part_data_dict.items():
            objetos = servico_dados.get("Objects", [])
            if servico_nome == "Workspace":
                workspace_content += processar_objetos_xml(objetos)
            else:
                outros_servicos += f'\n<Item class="Folder" referent="RBX_SERVICE_{servico_nome}">'
                outros_servicos += f'\n  <Properties><string name="Name">{servico_nome}</string></Properties>'
                outros_servicos += processar_objetos_xml(objetos)
                outros_servicos += '\n</Item>'
    elif isinstance(part_data_dict, list):
        workspace_content = processar_objetos_xml(part_data_dict)

    rbxlx_str = f'''<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">
    <External>null</External>
    <External>nil</External>
    <Item class="Workspace" referent="RBX_WORKSPACE">
        <Properties>
            <string name="Name">Workspace</string>
        </Properties>
        <Item class="SpawnLocation" referent="RBX_SPAWN">
            <Properties>
                <string name="Name">SpawnLocation</string>
                <bool name="Anchored">true</bool>
                <Vector3 name="Position"><X>0</X><Y>5</Y><Z>0</Z></Vector3>
                <Vector3 name="size"><X>12</X><Y>1</Y><Z>12</Z></Vector3>
            </Properties>
        </Item>
        {workspace_content}
    </Item>
    {outros_servicos}
</roblox>'''

    return rbxlx_str.encode('utf-8')

@app.route('/publicar', methods=['POST'])
def publicar():
    try:
        dados_json = request.json
        api_key = request.headers.get('x-api-key')
        universe_id = request.headers.get('universe-id')
        place_id = request.headers.get('place-id')

        if not api_key or not universe_id or not place_id:
            return jsonify({"erro": "Headers 'x-api-key', 'universe-id' e 'place-id' sao obrigatorios."}), 400

        conteudo_rbxlx = construir_rbxlx_completo(dados_json)
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
