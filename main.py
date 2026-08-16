from flask import Flask, request, jsonify
import requests
import xml.sax.saxutils as saxutils

app = Flask(__name__)

def processar_propriedade_xml(nome_prop, valor):
    """Traduz as propriedades coletadas do Lua diretamente para tags XML do Roblox"""
    if valor is None or nome_prop == "ClassName":
        return ""
    
    # Position, Size, Vector3
    if isinstance(valor, dict) and "X" in valor and "Y" in valor and "Z" in valor:
        return f'''
            <Vector3 name="{nome_prop}">
                <X>{valor["X"]}</X>
                <Y>{valor["Y"]}</Y>
                <Z>{valor["Z"]}</Z>
            </Vector3>'''
    
    # Color3 (R, G, B)
    elif isinstance(valor, dict) and "R" in valor and "G" in valor and "B" in valor:
        r = int(valor["R"] * 255) if isinstance(valor["R"], float) and valor["R"] <= 1.0 else int(valor["R"])
        g = int(valor["G"] * 255) if isinstance(valor["G"], float) and valor["G"] <= 1.0 else int(valor["G"])
        b = int(valor["B"] * 255) if isinstance(valor["B"], float) and valor["B"] <= 1.0 else int(valor["B"])
        
        cor_uint = (r << 16) | (g << 8) | b
        return f'\n            <Color3uint8 name="{nome_prop}">{cor_uint}</Color3uint8>'
    
    # Booleanos (Anchored, CanCollide, etc.)
    elif isinstance(valor, bool):
        val_str = "true" if valor else "false"
        return f'\n            <bool name="{nome_prop}">{val_str}</bool>'
    
    # Numeros (Transparency, Reflectance, etc.)
    elif isinstance(valor, (int, float)):
        if isinstance(valor, float):
            return f'\n            <float name="{nome_prop}">{valor}</float>'
        return f'\n            <int name="{nome_prop}">{valor}</int>'
    
    # Strings, Enums, Texturas e Imagens
    elif isinstance(valor, str):
        if "Enum." in valor:
            enum_val = valor.split(".")[-1]
            return f'\n            <token name="{nome_prop}">{enum_val}</token>'
        # Suporte para IDs e links de Imagem/Textura no Roblox XML
        if nome_prop in ["Texture", "Image", "TextureId", "ImageId"] or valor.startswith("rbxassetid://"):
            return f'\n            <Content name="{nome_prop}"><url>{saxutils.escape(valor)}</url></Content>'
        return f'\n            <string name="{nome_prop}">{saxutils.escape(valor)}</string>'
        
    return ""

def processar_objetos_xml(lista_objetos):
    xml_output = ""
    for idx, obj in enumerate(lista_objetos):
        props = obj.get("Properties", {})
        children = obj.get("Children", [])
        script_code = obj.get("Script")
        
        class_name = props.get("ClassName", "Part")
        obj_name = props.get("Name", f"Object_{idx}")
        
        # Garante ID limpo sem sinal negativo que quebra no XML
        id_unico = f"RBX_OBJ_{idx}_{abs(hash(obj_name))}"

        xml_output += f'\n<Item class="{class_name}" referent="{id_unico}">'
        xml_output += '\n  <Properties>'
        
        # Garante que peças fiquem fixas se não for especificado
        if "Anchored" not in props and class_name in ["Part", "WedgePart", "CornerWedgePart", "MeshPart"]:
            props["Anchored"] = True
            
        # Processa todas as propriedades da lista enviada pelo Lua
        for nome_prop, val_prop in props.items():
            xml_output += processar_propriedade_xml(nome_prop, val_prop)

        # Insere o código do Script na propriedade Source (para Script, LocalScript ou ModuleScript)
        if script_code or class_name in ["Script", "LocalScript", "ModuleScript"]:
            codigo_texto = str(script_code) if script_code is not None else ""
            codigo_escapado = saxutils.escape(codigo_texto)
            xml_output += f'\n            <ProtectedString name="Source">{codigo_escapado}</ProtectedString>'

        xml_output += '\n  </Properties>'
        
        if children:
            xml_output += processar_objetos_xml(children)
            
        xml_output += '\n</Item>'

    return xml_output

def construir_rbxlx_completo(part_data_dict):
    workspace_content = ""
    outros_servicos = ""

    # Mapeamento dos serviços oficiais do Roblox para não ficarem escondidos como "Folder"
    servicos_oficiais = {
        "ServerScriptService": "ServerScriptService",
        "ReplicatedStorage": "ReplicatedStorage",
        "ServerStorage": "ServerStorage",
        "StarterGui": "StarterGui",
        "StarterPack": "StarterPack",
        "Lighting": "Lighting",
        "SoundService": "SoundService"
    }

    if isinstance(part_data_dict, dict):
        for servico_nome, servico_dados in part_data_dict.items():
            objetos = servico_dados.get("Objects", [])
            if servico_nome == "Workspace":
                workspace_content += processar_objetos_xml(objetos)
            else:
                classe_servico = servicos_oficiais.get(servico_nome, "Folder")
                outros_servicos += f'\n<Item class="{classe_servico}" referent="RBX_SERVICE_{servico_nome}">'
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
            return jsonify({"erro": "Headers obrigatorios faltando."}), 400

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
